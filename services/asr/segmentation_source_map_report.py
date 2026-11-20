"""Audit reversible source mappings for saved native segment timestamps."""

import hashlib
import json
import subprocess
from pathlib import Path

from services.api.ingest import file_sha256
from services.asr.segmentation import map_native_segments_to_source
from services.asr.segmentation_candidate_runner import _reference, validate_suite
from services.immutable_reports import publish_json_once


MODES = ("fixed_window", "overlap_aware", "vad_cut_merge", "pause_aware")


def _map_chunk(chunk, sample_rate):
    window_id = chunk.get("window_id")
    window = {
        "window_id": window_id,
        "start_frame": chunk.get("start_frame"),
        "end_frame_exclusive": chunk.get("end_frame_exclusive"),
        "channel_index": chunk.get("channel_index"),
    }
    plan = {"sample_rate": sample_rate, "windows": [window]}
    segments = chunk.get("native_segments")
    if not isinstance(segments, list):
        raise ValueError("native_segment_timestamp_list_required")
    mapped = map_native_segments_to_source(plan, window_id, segments)
    return [
        {
            "segment_id": f"{window_id}:segment:{index:04d}",
            "window_id": window_id,
            "text_sha256": hashlib.sha256(row["text"].encode("utf-8")).hexdigest(),
            "window_start_frame": window["start_frame"],
            "window_end_frame_exclusive": window["end_frame_exclusive"],
            "local_start_ms": row["start_ms"],
            "local_end_ms": row["end_ms"],
            "source_start_frame": row["source_start_frame"],
            "source_end_frame_exclusive": row["source_end_frame_exclusive"],
            "source_start_ms": row["source_start_ms"],
            "source_end_ms": row["source_end_ms"],
            "source_window_channel_index": row["source_window_channel_index"],
            "source_timestamp_in_window": row["source_timestamp_in_window"],
            "source_mapping_kind": row["source_mapping_kind"],
            "source_round_trip_valid": row["source_round_trip_valid"],
        }
        for index, row in enumerate(mapped)
    ]


def build_source_map_report(receipt_paths, output_path, *, suite_path):
    suite_path, suite, _, manifest = validate_suite(suite_path)
    expected = {row["group_id"]: row for row in manifest["cases"]}
    if len(expected) != 16:
        raise ValueError("source_map_frozen_16_recording_cohort_required")
    by_mode = {}
    for raw_path in receipt_paths:
        path = Path(raw_path)
        report = json.loads(path.read_text(encoding="utf-8"))
        mode = report.get("configuration", {}).get("mode")
        if mode not in MODES or mode in by_mode or report.get("complete") is not True:
            raise ValueError("invalid_or_duplicate_source_map_receipt")
        by_mode[mode] = (path, report)
    if set(by_mode) != set(MODES):
        raise ValueError("all_source_map_mode_receipts_required")

    suite_sha256 = file_sha256(suite_path)
    profile_sha256 = next(
        row["source_profile_sha256"]
        for row in suite["jobs"]
        if row["candidate_id"] == "faster-whisper-tiny.en"
    )
    source_hashes = None
    receipts = {}
    mapped_hashes = {}
    modes = {}
    for mode in MODES:
        path, report = by_mode[mode]
        bindings = report.get("bindings", {})
        if (
            report.get("schema_version") != "asr_segmentation_mode_receipt_v1"
            or report.get("configuration", {}).get("profile_sha256") != profile_sha256
            or bindings.get("suite_sha256") != suite_sha256
            or bindings.get("manifest_sha256") != suite["manifest_sha256"]
            or not isinstance(bindings.get("source_sha256"), dict)
        ):
            raise ValueError("source_map_receipt_source_mismatch")
        if source_hashes is None:
            source_hashes = bindings["source_sha256"]
        elif bindings["source_sha256"] != source_hashes:
            raise ValueError("source_map_execution_source_mismatch")
        cases = {row["group_id"]: row for row in report.get("cases", [])}
        if set(cases) != set(expected):
            raise ValueError("source_map_receipt_cohort_mismatch")

        files = []
        totals = {
            "files": len(expected),
            "native_segments": 0,
            "mapped_segments": 0,
            "invalid_window_timestamps": 0,
            "round_trip_failures": 0,
        }
        for group_id, source in expected.items():
            case = cases[group_id]
            ref_sha = hashlib.sha256(_reference(source).encode("utf-8")).hexdigest()
            if (
                case.get("audio_sha256") != source["audio_sha256"]
                or case.get("reference_sha256") != ref_sha
                or case.get("failed")
            ):
                raise ValueError("source_map_case_source_or_failure_mismatch")
            chunks = case.get("chunks")
            if not isinstance(chunks, list) or len(chunks) != case.get("window_count"):
                raise ValueError("source_map_complete_window_rows_required")
            mapped_segments = []
            for chunk in chunks:
                native = chunk.get("native_segments")
                if not isinstance(native, list):
                    raise ValueError("native_segment_timestamp_list_required")
                rows = _map_chunk(chunk, 16000)
                if len(rows) != len(native):
                    raise ValueError("source_map_segment_count_mismatch")
                mapped_segments.extend(rows)
            valid = [
                row for row in mapped_segments if row["source_timestamp_in_window"]
            ]
            invalid = [
                row for row in mapped_segments if not row["source_timestamp_in_window"]
            ]
            round_trip_failures = sum(
                row["source_timestamp_in_window"] and not row["source_round_trip_valid"]
                for row in mapped_segments
            )
            for row in mapped_segments:
                key = (group_id, row["segment_id"])
                if key in mapped_hashes:
                    raise ValueError("duplicate_stable_source_segment_id")
                mapped_hashes[key] = (row["text_sha256"], row["window_id"])
            file_summary = {
                "native_segments": len(mapped_segments),
                "mapped_segments": len(valid),
                "invalid_window_timestamps": len(invalid),
                "round_trip_failures": round_trip_failures,
            }
            for key in file_summary:
                totals[key] += file_summary[key]
            files.append(
                {
                    "group_id": group_id,
                    "audio_sha256": case["audio_sha256"],
                    "reference_sha256": ref_sha,
                    "summary": file_summary,
                    "segments": mapped_segments,
                }
            )
            receipts.setdefault(group_id, (case["audio_sha256"], ref_sha))
        modes[mode] = {
            "receipt_path": path.as_posix(),
            "receipt_sha256": file_sha256(path),
            "receipt_source_commit": report.get("source_commit"),
            "summary": totals,
            "files": files,
        }
    if set(receipts) != set(expected):
        raise ValueError("source_map_missing_case_inputs")

    result = {
        "schema_version": "asr_segmentation_source_map_matrix_v1",
        "complete": True,
        "clinical_acceptance": False,
        "automatic_promotion": False,
        "inference_executed": False,
        "generator_source_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "suite_sha256": suite_sha256,
        "manifest_sha256": suite["manifest_sha256"],
        "candidate_id": "faster-whisper-tiny.en",
        "profile_sha256": profile_sha256,
        "source_execution_sha256": source_hashes,
        "case_count": len(expected),
        "native_segment_count": sum(
            mode["summary"]["native_segments"] for mode in modes.values()
        ),
        "source_frame_mapping": {
            "sample_rate": 16000,
            "local_timestamp_conversion": "round(milliseconds * sample_rate / 1000)",
            "invalid_native_timestamps": "retain_window_id; source frame bounds null; never clamp",
            "overlap_policy": "duplicate window mappings preserved and tied to stable window ID",
        },
        "modes": modes,
        "limitations": [
            "Native decoder segment timestamps are not word-level alignments or proof of acoustic boundaries.",
            "Original mode receipts predate source commit fields; their exact execution-source hashes are preserved.",
            "This source-map candidate runner is not integrated into the production transcript publication path.",
            "Resampled audio requires an explicit measured group-delay mapping contract.",
        ],
    }
    return publish_json_once(output_path, result)
