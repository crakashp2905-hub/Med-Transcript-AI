"""Reconcile source-timed turn boundaries against saved ASR windows."""

import hashlib
import json
import subprocess
import wave
from pathlib import Path

from services.api.ingest import file_sha256
from services.asr.segmentation import diagnose_boundaries
from services.asr.segmentation_candidate_runner import _reference, validate_suite
from services.immutable_reports import publish_json_once


MODES = ("fixed_window", "overlap_aware", "vad_cut_merge", "pause_aware")
SUMMARY_FIELDS = (
    "annotated_turns",
    "omitted_short_turns",
    "clipped_turns",
    "partially_uncovered_turns",
    "windows_joining_known_roles",
    "windows_with_unknown_role_turns",
)


def _source_turns(case, sample_rate, total_frames):
    result = []
    for index, row in enumerate(case.get("reference_turns", [])):
        start_ms, end_ms = row.get("start_ms"), row.get("end_ms")
        if (
            type(start_ms) not in (int, float)
            or type(end_ms) not in (int, float)
            or not 0 <= start_ms < end_ms
        ):
            raise ValueError("invalid_reference_turn_interval")
        start_frame = round(start_ms * sample_rate / 1000)
        end_frame = round(end_ms * sample_rate / 1000)
        if not 0 <= start_frame < end_frame <= total_frames:
            raise ValueError("reference_turn_outside_source_audio")
        role = row.get("role")
        if role is not None and not isinstance(role, str):
            raise ValueError("invalid_reference_turn_role")
        result.append(
            {
                "turn_id": f"{case['group_id']}:turn:{index:04d}",
                "start_frame": start_frame,
                "end_frame": end_frame,
                "role": role,
            }
        )
    if not result:
        raise ValueError("timed_reference_turns_required")
    return result


def _audio_shape(path, expected_sha256):
    if file_sha256(path) != expected_sha256:
        raise ValueError("segmentation_boundary_audio_hash_mismatch")
    try:
        with wave.open(str(path), "rb") as audio:
            shape = {
                "channels": audio.getnchannels(),
                "sample_width_bytes": audio.getsampwidth(),
                "sample_rate": audio.getframerate(),
                "total_frames": audio.getnframes(),
                "compression": audio.getcomptype(),
            }
    except (wave.Error, EOFError, OSError):
        raise ValueError("segmentation_boundary_invalid_wave") from None
    if (
        shape["channels"] != 1
        or shape["sample_width_bytes"] != 2
        or shape["sample_rate"] != 16000
        or shape["total_frames"] <= 0
        or shape["compression"] != "NONE"
    ):
        raise ValueError("segmentation_boundary_requires_mono_16khz_pcm16")
    return shape


def _window_rows(case):
    chunks = case.get("chunks")
    if (
        not isinstance(chunks, list)
        or not chunks
        or len(chunks) != case.get("window_count")
    ):
        raise ValueError("segmentation_boundary_complete_window_receipt_required")
    result = []
    seen = set()
    for row in chunks:
        start, end, window_id = (
            row.get("start_frame"),
            row.get("end_frame_exclusive"),
            row.get("window_id"),
        )
        if (
            not isinstance(window_id, str)
            or window_id in seen
            or type(start) is not int
            or type(end) is not int
            or start < 0
            or end <= start
        ):
            raise ValueError("invalid_segmentation_window_receipt")
        seen.add(window_id)
        result.append(
            {
                "window_id": window_id,
                "start_frame": start,
                "end_frame_exclusive": end,
            }
        )
    return result


def _diagnose_case(source, case, audio_path, short_turn_frames):
    shape = _audio_shape(audio_path, source["audio_sha256"])
    reference = _reference(source)
    if case.get("audio_sha256") != source["audio_sha256"]:
        raise ValueError("segmentation_boundary_case_audio_mismatch")
    if (
        case.get("reference_sha256")
        != hashlib.sha256(reference.encode("utf-8")).hexdigest()
    ):
        raise ValueError("segmentation_boundary_case_reference_mismatch")
    turns = _source_turns(source, shape["sample_rate"], shape["total_frames"])
    windows = _window_rows(case)
    if any(window["end_frame_exclusive"] > shape["total_frames"] for window in windows):
        raise ValueError("segmentation_window_outside_source_audio")
    diagnostics = diagnose_boundaries(turns, windows, short_turn_frames)
    turn_by_id = {turn["turn_id"]: turn for turn in turns}
    diagnostic_turns = [
        {
            **row,
            "start_frame": turn_by_id[row["turn_id"]]["start_frame"],
            "end_frame": turn_by_id[row["turn_id"]]["end_frame"],
        }
        for row in diagnostics["turns"]
    ]
    window_by_id = {window["window_id"]: window for window in windows}
    diagnostic_windows = [
        {**window_by_id[row["window_id"]], **row} for row in diagnostics["windows"]
    ]
    return {
        "group_id": source["group_id"],
        "condition": source["condition"],
        "audio_sha256": source["audio_sha256"],
        "reference_sha256": case["reference_sha256"],
        "sample_rate": shape["sample_rate"],
        "total_frames": shape["total_frames"],
        "annotated_turn_count": len(turns),
        "segmentation_window_count": len(windows),
        "summary": diagnostics["summary"],
        "turns": diagnostic_turns,
        "windows": diagnostic_windows,
    }


def build_boundary_report(
    receipt_paths,
    output_path,
    *,
    suite_path,
    short_turn_threshold_ms=100,
):
    if (
        type(short_turn_threshold_ms) is not int
        or not 0 <= short_turn_threshold_ms <= 5000
    ):
        raise ValueError("invalid_short_turn_threshold_ms")
    suite_path, suite, _, manifest = validate_suite(suite_path)
    expected = {case["group_id"]: case for case in manifest["cases"]}
    if len(expected) != 16:
        raise ValueError("segmentation_boundary_frozen_16_recording_cohort_required")
    by_mode = {}
    for raw_path in receipt_paths:
        path = Path(raw_path)
        report = json.loads(path.read_text(encoding="utf-8"))
        mode = report.get("configuration", {}).get("mode")
        if mode not in MODES or mode in by_mode or report.get("complete") is not True:
            raise ValueError("invalid_or_duplicate_segmentation_boundary_receipt")
        by_mode[mode] = (path, report)
    if set(by_mode) != set(MODES):
        raise ValueError("all_segmentation_boundary_mode_receipts_required")

    suite_sha256 = file_sha256(suite_path)
    expected_profile_sha256 = next(
        row["source_profile_sha256"]
        for row in suite["jobs"]
        if row["candidate_id"] == "faster-whisper-tiny.en"
    )
    source_commits = {}
    source_digests = None
    reference_hashes = {}
    input_hashes = {}
    mode_reports = {}
    short_turn_frames = round(short_turn_threshold_ms * 16000 / 1000)
    audio_root = Path(suite["audio_root"])

    for mode in MODES:
        path, report = by_mode[mode]
        bindings = report.get("bindings", {})
        if (
            report.get("schema_version") != "asr_segmentation_mode_receipt_v1"
            or report.get("configuration", {}).get("profile_sha256")
            != expected_profile_sha256
            or bindings.get("suite_sha256") != suite_sha256
            or bindings.get("manifest_sha256") != suite["manifest_sha256"]
            or not report.get("source_commit")
            or not isinstance(bindings.get("source_sha256"), dict)
        ):
            raise ValueError("segmentation_boundary_receipt_source_mismatch")
        if source_digests is None:
            source_digests = bindings["source_sha256"]
        elif bindings["source_sha256"] != source_digests:
            raise ValueError("segmentation_boundary_execution_source_mismatch")
        source_commits[mode] = report["source_commit"]
        cases = {case["group_id"]: case for case in report.get("cases", [])}
        if set(cases) != set(expected):
            raise ValueError("segmentation_boundary_receipt_cohort_mismatch")

        files = []
        totals = {field: 0 for field in SUMMARY_FIELDS}
        totals["files"] = len(expected)
        totals["segmentation_windows"] = 0
        for group_id, source in expected.items():
            case = cases[group_id]
            audio_path = audio_root / source["audio"]
            row = _diagnose_case(
                source, case, audio_path, short_turn_frames=short_turn_frames
            )
            if (
                group_id in reference_hashes
                and reference_hashes[group_id] != row["reference_sha256"]
            ):
                raise ValueError("segmentation_boundary_reference_changed_across_modes")
            if (
                group_id in input_hashes
                and input_hashes[group_id] != row["audio_sha256"]
            ):
                raise ValueError("segmentation_boundary_audio_changed_across_modes")
            reference_hashes[group_id] = row["reference_sha256"]
            input_hashes[group_id] = row["audio_sha256"]
            totals["segmentation_windows"] += row["segmentation_window_count"]
            for field in SUMMARY_FIELDS:
                totals[field] += row["summary"][field]
            files.append(row)
        mode_reports[mode] = {
            "receipt_path": path.as_posix(),
            "receipt_sha256": file_sha256(path),
            "source_commit": report["source_commit"],
            "summary": totals,
            "files": files,
        }

    result = {
        "schema_version": "asr_segmentation_boundary_matrix_v1",
        "complete": True,
        "clinical_acceptance": False,
        "automatic_promotion": False,
        "generator_source_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "suite_sha256": suite_sha256,
        "manifest_sha256": suite["manifest_sha256"],
        "candidate_id": "faster-whisper-tiny.en",
        "profile_sha256": expected_profile_sha256,
        "source_commits": source_commits,
        "execution_source_sha256": source_digests,
        "case_count": len(expected),
        "input_hash_equivalence": "same_audio_and_reference_hashes_across_all_modes",
        "turn_time_mapping": {
            "source_units": "milliseconds",
            "target_units": "source_pcm_frames",
            "mapping": "round(milliseconds * sample_rate / 1000)",
            "short_turn_threshold_ms": short_turn_threshold_ms,
            "short_turn_threshold_frames": short_turn_frames,
        },
        "boundary_metric_scope": "reference_turn_interval_intersections_not_word_alignment",
        "modes": mode_reports,
        "limitations": [
            "Reference turn intervals are development annotations, not independently adjudicated clinical gold.",
            "Clipped counts indicate turn intervals crossed by a window edge; they do not measure word-edge timing error.",
            "Joined known roles are window-level overlap indicators, not speaker diarization error rates.",
            "Window intersection does not prove that the audio contains or omits speech within each annotated interval.",
        ],
    }
    return publish_json_once(output_path, result)
