"""Matched local evaluation for source-coordinate segmentation strategies.

Energy-derived intervals are development heuristics, not annotated speech truth.
Channel-first evaluation requires multichannel source recordings and is reported
as unavailable when the frozen cohort does not provide them.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import re
import tempfile
import time
import wave
from pathlib import Path

from services.api.ingest import file_sha256
from services.asr.segmentation import plan_segments, stitch_window_outputs
from services.asr.vad_candidates import ENERGY_RMS_V1, detect_file
from services.detailed_benchmark import fast_score, load, process_peak_resident_bytes
from services.evidence_io import atomic_json
from services.immutable_reports import publish_json_once

MODE_CONFIGS = {
    "fixed_window": {"max_window_ms": 30000},
    "overlap_aware": {"max_window_ms": 30000, "overlap_ms": 2000},
    "vad_cut_merge": {
        "max_window_ms": 30000,
        "min_window_ms": 5000,
        "padding_ms": 300,
    },
    "pause_aware": {"max_window_ms": 30000},
}
ACTIVITY_PROFILE = {
    **ENERGY_RMS_V1,
    "candidate_id": "energy_rms_merge_1000ms_v1",
    "merge_silence_ms": 1000,
}
ARM_IDS = tuple(MODE_CONFIGS)


def _reference(case):
    return " ".join(
        re.sub(r"<[^>]+>", "", turn["reference"]) for turn in case["reference_turns"]
    )


def validate_suite(suite_path):
    suite_path = Path(suite_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest_path = Path(suite["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    lock = json.loads((manifest_path.parent / "lock.json").read_text(encoding="utf-8"))
    if (
        file_sha256(manifest_path) != suite["manifest_sha256"]
        or lock["manifest_sha256"] != suite["manifest_sha256"]
    ):
        raise ValueError("segmentation_manifest_lock_mismatch")
    if suite.get("maximum_normalized_wer") != 0.05:
        raise ValueError("segmentation_wer_gate_changed")
    reservation = json.loads(
        Path("evaluation/acceptance-reservation-v1.json").read_text(encoding="utf-8")
    )
    reserved = set(reservation["reserved_groups"])
    if any(
        case["foreground_id"] in reserved or case.get("donor_id") in reserved
        for case in manifest["cases"]
    ):
        raise ValueError("segmentation_acceptance_group_leakage")
    for name, digest in suite.get("source_text_sha256", {}).items():
        if file_sha256(name) != digest:
            raise ValueError("segmentation_frozen_benchmark_source_changed")
    return suite_path, suite, manifest_path, manifest


def _require_whisper_runtime():
    try:
        version = importlib.metadata.version("faster-whisper")
    except importlib.metadata.PackageNotFoundError:
        raise ValueError("segmentation_faster_whisper_unavailable") from None
    if version != "1.2.1":
        raise ValueError("segmentation_faster_whisper_version_mismatch")


def _read_pcm(path, expected_sha256):
    if file_sha256(path) != expected_sha256:
        raise ValueError("segmentation_source_audio_hash_mismatch")
    with wave.open(str(path), "rb") as source:
        channels, rate, width, frames = (
            source.getnchannels(),
            source.getframerate(),
            source.getsampwidth(),
            source.getnframes(),
        )
        if width != 2 or rate != 16000 or channels != 1 or frames <= 0:
            raise ValueError("segmentation_requires_mono_16khz_pcm16_source")
        pcm = source.readframes(frames)
    return pcm, frames, rate


def _activity_spans(path, sample_rate):
    activity = detect_file(path, ACTIVITY_PROFILE)
    spans = [
        (row["start_ms"] * sample_rate // 1000, row["end_ms"] * sample_rate // 1000)
        for row in activity["speech_intervals_ms"]
    ]
    pauses = [
        (left[1], right[0])
        for left, right in zip(spans, spans[1:])
        if right[0] - left[1] >= sample_rate // 5
    ]
    return activity, spans, pauses


def build_plan(path, frames, rate, mode):
    if mode not in MODE_CONFIGS:
        raise ValueError("unsupported_segmentation_mode")
    activity, speech_spans, pauses = _activity_spans(path, rate)
    if not speech_spans:
        raise ValueError("energy_activity_candidate_has_no_spans")
    kwargs = dict(MODE_CONFIGS[mode])
    if mode == "vad_cut_merge":
        kwargs.update(vad_spans=speech_spans, speech_spans=speech_spans)
    elif mode == "pause_aware":
        kwargs.update(pause_spans=pauses, speech_spans=speech_spans)
    else:
        kwargs.update(speech_spans=speech_spans)
    plan = plan_segments(frames, rate, mode, **kwargs)
    plan["activity_candidate"] = {
        "candidate_id": activity["candidate_id"],
        "candidate_sha256": activity["candidate_sha256"],
        "score_kind": activity["score_kind"],
        "speech_intervals_ms": activity["speech_intervals_ms"],
    }
    plan["coverage_scope"] = "energy_heuristic_activity_spans_not_annotated_speech"
    return plan


def evaluate_case(case, audio_path, predictor, mode):
    started = time.perf_counter()
    pcm, frames, rate = _read_pcm(audio_path, case["audio_sha256"])
    plan = build_plan(audio_path, frames, rate, mode)
    predictions = []
    chunk_rows = []
    with tempfile.TemporaryDirectory(prefix="asr-segmentation-") as temporary:
        crop_path = Path(temporary) / "window.wav"
        for window in plan["windows"]:
            start = window["start_frame"]
            end = window["end_frame_exclusive"]
            with wave.open(str(crop_path), "wb") as crop:
                crop.setparams((1, 2, rate, 0, "NONE", "not compressed"))
                crop.writeframes(pcm[start * 2 : end * 2])
            chunk_started = time.perf_counter()
            failed = False
            failure_code = None
            native_segments = None
            try:
                decoded = predictor(crop_path, False)
                text = decoded.get("text")
                native_segments = decoded.get("segments")
                if not isinstance(text, str) or len(text) > 500000:
                    raise ValueError("invalid_segmentation_decoder_text")
                text.encode("utf-8")
                if native_segments is not None:
                    if not isinstance(native_segments, list) or any(
                        not isinstance(segment, dict)
                        or not isinstance(segment.get("text"), str)
                        for segment in native_segments
                    ):
                        raise ValueError("invalid_segmentation_decoder_segments")
                    native_segments = [
                        {
                            **segment,
                            "source_start_ms": start / 16 + segment.get("start_ms", 0),
                            "source_end_ms": start / 16 + segment.get("end_ms", 0),
                            "source_timestamp_in_window": (
                                isinstance(segment.get("start_ms"), (int, float))
                                and isinstance(segment.get("end_ms"), (int, float))
                                and math.isfinite(segment["start_ms"])
                                and math.isfinite(segment["end_ms"])
                                and 0
                                <= segment["start_ms"]
                                <= segment["end_ms"]
                                <= (end - start) / 16
                            ),
                        }
                        for segment in native_segments
                    ]
            except Exception as exc:
                failed = True
                failure_code = type(exc).__name__
                text = ""
                native_segments = None
            predictions.append({"window_id": window["window_id"], "text": text})
            chunk_rows.append(
                {
                    "window_id": window["window_id"],
                    "start_frame": start,
                    "end_frame_exclusive": end,
                    "failed": failed,
                    "failure_code": failure_code,
                    "hypothesis": text,
                    "native_segments": native_segments,
                    "wall_seconds": time.perf_counter() - chunk_started,
                }
            )
    stitched = stitch_window_outputs(plan, predictions)
    failed = any(row["failed"] for row in chunk_rows)
    hypothesis = "" if failed else stitched["text"]
    reference = _reference(case)
    score = fast_score(reference, hypothesis)
    return {
        "group_id": case["group_id"],
        "condition": case["condition"],
        "foreground_id": case["foreground_id"],
        "donor_id": case.get("donor_id"),
        "audio_sha256": case["audio_sha256"],
        "reference_sha256": hashlib.sha256(reference.encode("utf-8")).hexdigest(),
        "reference": reference,
        "hypothesis": hypothesis,
        "failed": failed,
        "failure_policy": "any_failed_window_empty_hypothesis_full_reference_deletion",
        "window_count": len(plan["windows"]),
        "coverage_ledger": plan["coverage_ledger"],
        "coverage_scope": plan["coverage_scope"],
        "activity_candidate": plan["activity_candidate"],
        "stitch_events": stitched["stitch_events"],
        "review_required": stitched["review_required"],
        "timestamp_kind": stitched["timestamp_kind"],
        "chunks": chunk_rows,
        "wall_seconds": time.perf_counter() - started,
        **score,
    }


def run_mode(
    suite_path, mode, output_path, *, resume=False, compute_budget_seconds=7200
):
    if mode not in MODE_CONFIGS:
        raise ValueError("unsupported_segmentation_mode")
    if type(compute_budget_seconds) is not int or compute_budget_seconds <= 0:
        raise ValueError("positive_segmentation_compute_budget_required")
    suite_path, suite, manifest_path, manifest = validate_suite(suite_path)
    _require_whisper_runtime()
    job = next(
        row for row in suite["jobs"] if row["candidate_id"] == "faster-whisper-tiny.en"
    )
    output_path = Path(output_path)
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial")
    if output_path.exists():
        raise ValueError("preserve_existing_segmentation_report")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_files = [
        Path(__file__),
        Path("services/asr/segmentation.py"),
        Path("services/asr/vad_candidates.py"),
        Path("services/asr/profiles.py"),
        Path("services/detailed_benchmark.py"),
        Path("services/conversation_experiment.py"),
        Path("services/clinical_metrics.py"),
        Path("services/immutable_reports.py"),
        Path("services/evidence_io.py"),
    ]
    source_sha256 = {
        path.resolve().as_posix(): file_sha256(path) for path in source_files
    }
    profile_sha256 = job["source_profile_sha256"]
    config = {
        "candidate_id": "faster-whisper-tiny.en",
        "profile_sha256": profile_sha256,
        "runtime_version": "1.2.1",
        "mode": mode,
        "mode_parameters": MODE_CONFIGS[mode],
        "activity_profile": ACTIVITY_PROFILE,
        "activity_profile_sha256": hashlib.sha256(
            json.dumps(ACTIVITY_PROFILE, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "compute_budget_seconds": compute_budget_seconds,
        "failure_policy": "any_failed_window_empty_hypothesis_full_reference_deletion",
        "training_group_scope": "same_pretrained_weights_no_project_finetuning",
    }
    bindings = {
        "suite_sha256": file_sha256(suite_path),
        "manifest_sha256": suite["manifest_sha256"],
        "profile_file_sha256": file_sha256(Path("data") / job["profile_file"]),
        "profile_sha256": profile_sha256,
        "source_sha256": source_sha256,
    }
    if checkpoint_path.exists():
        if not resume:
            raise ValueError("partial_segmentation_run_exists_resume_or_preserve_it")
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if (
            checkpoint.get("bindings") != bindings
            or checkpoint.get("configuration") != config
        ):
            raise ValueError("segmentation_resume_configuration_changed")
    else:
        if resume:
            raise ValueError("segmentation_resume_checkpoint_missing")
        checkpoint = {
            "schema_version": "segmentation_mode_checkpoint_v1",
            "bindings": bindings,
            "configuration": config,
            "cases": [],
        }
        atomic_json(checkpoint_path, checkpoint)

    load_started = time.perf_counter()
    cpu_started = time.process_time()
    predictor, runtime, close = load(job)
    model_load_seconds = time.perf_counter() - load_started
    done = {row["group_id"] for row in checkpoint["cases"]}
    try:
        for case in manifest["cases"]:
            if case["group_id"] in done:
                continue
            audio_path = Path(suite["audio_root"]) / case["audio"]
            if file_sha256(audio_path) != case["audio_sha256"]:
                raise ValueError("segmentation_source_audio_changed")
            try:
                row = evaluate_case(case, audio_path, predictor, mode)
            except Exception as exc:
                reference = _reference(case)
                score = fast_score(reference, "")
                row = {
                    "group_id": case["group_id"],
                    "condition": case["condition"],
                    "foreground_id": case["foreground_id"],
                    "donor_id": case.get("donor_id"),
                    "audio_sha256": case["audio_sha256"],
                    "reference_sha256": hashlib.sha256(reference.encode()).hexdigest(),
                    "reference": reference,
                    "hypothesis": "",
                    "failed": True,
                    "failure_code": type(exc).__name__,
                    "failure_policy": "any_failed_window_empty_hypothesis_full_reference_deletion",
                    "window_count": 0,
                    "coverage_ledger": None,
                    "coverage_scope": "unavailable",
                    "chunks": [],
                    "wall_seconds": 0.0,
                    **score,
                }
            checkpoint["cases"].append(row)
            checkpoint["cases"].sort(key=lambda item: item["group_id"])
            elapsed = sum(item["wall_seconds"] for item in checkpoint["cases"])
            if elapsed > compute_budget_seconds:
                atomic_json(checkpoint_path, checkpoint)
                raise TimeoutError("segmentation_mode_compute_budget_exceeded")
            atomic_json(checkpoint_path, checkpoint)
            print(
                json.dumps(
                    {
                        "mode": mode,
                        "group_id": case["group_id"],
                        "cases_complete": len(checkpoint["cases"]),
                        "failed": row["failed"],
                        "wall_seconds": round(row["wall_seconds"], 2),
                    }
                ),
                flush=True,
            )
    finally:
        close()
    if len(checkpoint["cases"]) != len(manifest["cases"]):
        raise ValueError("segmentation_mode_case_coverage_incomplete")
    mode_summary = _summarize(checkpoint["cases"])
    try:
        peak_bytes, peak_method = process_peak_resident_bytes()
        resource = {
            "status": "measured",
            "peak_resident_bytes": peak_bytes,
            "method": peak_method,
        }
    except (OSError, ImportError, AttributeError):
        resource = {
            "status": "unavailable",
            "peak_resident_bytes": None,
            "method": None,
        }
    report = {
        "schema_version": "asr_segmentation_mode_receipt_v1",
        "complete": True,
        "clinical_acceptance": False,
        "automatic_promotion": False,
        "reference_status": manifest.get("clinician_adjudication", "unknown"),
        "bindings": bindings,
        "configuration": config,
        "runtime": runtime,
        "model_load_seconds": model_load_seconds,
        "process_cpu_seconds": time.process_time() - cpu_started,
        "mode_wall_seconds": sum(row["wall_seconds"] for row in checkpoint["cases"]),
        "resource_measurement": resource,
        "summary": mode_summary,
        "cases": checkpoint["cases"],
        "notes": [
            "Energy RMS spans are uncalibrated proxy annotations, not validated speech truth.",
            "Window coverage is guaranteed against those proxy spans; no independently annotated speech-span set was available.",
            "Any overlap-token removal requires audio review; the stitched timing is window-approximation-only.",
            "This development report does not qualify the ASR model or establish clinical correctness.",
        ],
    }
    published = publish_json_once(output_path, report)
    checkpoint_path.unlink(missing_ok=True)
    return published


def _summarize(rows):
    words = sum(row["reference_words"] for row in rows)
    edits = sum(row["normalized_edits"] for row in rows)
    return {
        "sample_count": len(rows),
        "failed_samples": sum(row["failed"] for row in rows),
        "reference_words": words,
        "normalized_edits": edits,
        "normalized_wer": edits / words if words else None,
        "wer_admission_maximum": 0.05,
        "wer_admission": "pass" if words and edits / words <= 0.05 else "fail",
        "wall_seconds": sum(row["wall_seconds"] for row in rows),
    }


def combine_receipts(receipt_paths, output_path, *, suite_path):
    suite_path, suite, manifest_path, manifest = validate_suite(suite_path)
    receipts = [
        (Path(path), json.loads(Path(path).read_text(encoding="utf-8")))
        for path in receipt_paths
    ]
    by_mode = {}
    for path, report in receipts:
        mode = report.get("configuration", {}).get("mode")
        if mode not in MODE_CONFIGS or mode in by_mode or not report.get("complete"):
            raise ValueError("invalid_or_duplicate_segmentation_mode_receipt")
        by_mode[mode] = (path, report)
    if set(by_mode) != set(MODE_CONFIGS):
        raise ValueError("all_applicable_segmentation_mode_receipts_required")
    expected = {case["group_id"]: case for case in manifest["cases"]}
    reference_hashes = {}
    common_hashes = {}
    modes = {}
    common_sources = None
    for mode, (path, report) in by_mode.items():
        if (
            report["bindings"]["suite_sha256"] != file_sha256(suite_path)
            or report["bindings"]["manifest_sha256"] != suite["manifest_sha256"]
            or report["configuration"]["profile_sha256"]
            != suite["jobs"][0]["source_profile_sha256"]
        ):
            raise ValueError("segmentation_mode_receipt_source_mismatch")
        if report["configuration"] != {
            **report["configuration"],
            "mode": mode,
            "mode_parameters": MODE_CONFIGS[mode],
        }:
            raise ValueError("segmentation_mode_configuration_mismatch")
        source_digests = report["bindings"].get("source_sha256")
        if not isinstance(source_digests, dict):
            raise ValueError("segmentation_mode_source_digests_required")
        if common_sources is None:
            common_sources = source_digests
        elif source_digests != common_sources:
            raise ValueError("segmentation_mode_runner_sources_changed")
        rows = {row["group_id"]: row for row in report["cases"]}
        if set(rows) != set(expected):
            raise ValueError("segmentation_mode_cohort_mismatch")
        for group_id, row in rows.items():
            source = expected[group_id]
            if (
                row["audio_sha256"] != source["audio_sha256"]
                or row["condition"] != source["condition"]
                or row["foreground_id"] != source["foreground_id"]
                or row["donor_id"] != source.get("donor_id")
            ):
                raise ValueError("segmentation_mode_input_mismatch")
            expected_reference_sha = hashlib.sha256(
                _reference(source).encode("utf-8")
            ).hexdigest()
            if row["reference_sha256"] != expected_reference_sha:
                raise ValueError("segmentation_mode_reference_mismatch")
            if row["failed"] and row["hypothesis"]:
                raise ValueError("failed_segmentation_case_must_be_deletion")
            ref_sha = row["reference_sha256"]
            if group_id in reference_hashes and reference_hashes[group_id] != ref_sha:
                raise ValueError("segmentation_reference_changed_across_modes")
            reference_hashes[group_id] = ref_sha
            common_hashes.setdefault(group_id, set()).add(row["audio_sha256"])
        modes[mode] = {
            "path": path.as_posix(),
            "sha256": file_sha256(path),
            "configuration": report["configuration"],
            "summary": report["summary"],
            "resource_measurement": report["resource_measurement"],
            "cases": report["cases"],
        }
    if any(len(hashes) != 1 for hashes in common_hashes.values()):
        raise ValueError("segmentation_input_hashes_changed_across_modes")
    channels = {
        "status": "not_applicable",
        "reason": "all_16_frozen_source_files_are_mono; channel_first_requires_multichannel_audio",
        "same_input_manifest_sha256": suite["manifest_sha256"],
    }
    report = {
        "schema_version": "asr_segmentation_candidate_matrix_v1",
        "complete": False,
        "applicable_modes_complete": True,
        "clinical_acceptance": False,
        "automatic_promotion": False,
        "suite_sha256": file_sha256(suite_path),
        "manifest_sha256": suite["manifest_sha256"],
        "case_count": len(expected),
        "input_hash_equivalence": "same_audio_sha256_for_every_case_across_all_applicable_modes",
        "wer_admission_maximum": 0.05,
        "modes": modes,
        "channel_first": channels,
        "limitations": [
            "Channel-first cannot be evaluated on the frozen mono cohort.",
            "Energy activity spans are a heuristic and do not prove that all real speech is covered.",
            "No independently annotated word or speech-span reference is available.",
            "WER is development-only and all modes remain subject to the unchanged 5% admission threshold.",
        ],
    }
    return publish_json_once(output_path, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite", default="evaluation/detailed-suite-v7-segmentation-planner.json"
    )
    parser.add_argument("--mode", choices=[*MODE_CONFIGS, "combine"], required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--receipts", nargs="*")
    parser.add_argument("--compute-budget-seconds", type=int, default=7200)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.mode == "combine":
        result = combine_receipts(
            args.receipts or [], args.output, suite_path=args.suite
        )
    else:
        result = run_mode(
            args.suite,
            args.mode,
            args.output,
            resume=args.resume,
            compute_budget_seconds=args.compute_budget_seconds,
        )
    print(
        json.dumps(
            result.get("summary", {"matrix_complete": result["complete"]}),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
