"""Paired, local-only enhancement screen over the frozen PriMock smoke set."""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from services.audio_enhancement import (
    highpass_transform,
    normalize_rms_transform,
    prepare_candidate,
    spectral_gate_transform,
)
from services.audio_provenance import file_sha256
from services.evaluation import PROJECT_MAX_NORMALIZED_WER, score, wer_gate
from services.evidence_io import atomic_json


def _summary(rows):
    reference_words = sum(row["reference_words"] for row in rows)
    normalized_edits = sum(row["normalized_edits"] for row in rows)
    raw_reference_words = sum(row["raw_reference_words"] for row in rows)
    raw_edits = sum(row["raw_edits"] for row in rows)
    failed = sum(row["status"] == "failed" for row in rows)
    return {
        "sample_count": len(rows),
        "failed_samples": failed,
        "reference_words": reference_words,
        "normalized_edits": normalized_edits,
        "normalized_wer": normalized_edits / reference_words
        if reference_words
        else None,
        "raw_reference_words": raw_reference_words,
        "raw_edits": raw_edits,
        "raw_wer": raw_edits / raw_reference_words if raw_reference_words else None,
        "admission_gate": wer_gate(
            {
                "reference_words": reference_words,
                "normalized_edits": normalized_edits,
                "failed_samples": failed,
            },
            PROJECT_MAX_NORMALIZED_WER,
        ),
    }


def run(
    manifest_path="evaluation/datasets/primock57-smoke-v1/manifest.json",
    audio_root="data/datasets/primock57-smoke",
    baseline_run="evaluation/runs/primock57-smoke-v1/omi-med-stt-v1.json",
    output_path="evaluation/reports/audio-enhancement-paired-v1.json",
    model_dir="data/models/omi-med-stt-v1-gguf",
    omi_cache="data/omi-cache",
    package_dir="data/benchmark-runtime",
):
    output, manifest_file, baseline_file = (
        Path(output_path),
        Path(manifest_path),
        Path(baseline_run),
    )
    if output.exists():
        raise ValueError("Preserve previous enhancement evidence; choose a new output")
    manifest_hash, baseline_hash = (
        file_sha256(manifest_file),
        file_sha256(baseline_file),
    )
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    baseline_run_data = json.loads(baseline_file.read_text(encoding="utf-8"))
    if (
        manifest.get("data_class") != "approved_public"
        or not manifest.get("rights_reviewed")
        or manifest_hash != baseline_run_data.get("manifest_sha256")
        or len(manifest.get("samples", [])) != baseline_run_data.get("sample_count")
    ):
        raise ValueError("Frozen public evaluation manifest and baseline must match")
    runtime_config = baseline_run_data["runtime_configuration"]
    if runtime_config.get("engine") != "omi":
        raise ValueError("Pinned Omi baseline required")

    package = Path(package_dir).resolve()
    model = Path(model_dir).resolve()
    cache = Path(omi_cache).resolve()
    sys.path.insert(0, str(package))
    os.environ["OMI_MED_STT_CACHE"] = str(cache)
    os.environ["OMI_MED_STT_CPP_REQUIRE_PREBUILT"] = "1"
    from omi_stt import cpp_runtime
    from services.omi_adapter import OmiPredictor

    if not cpp_runtime._cached_parakeet_lib().is_file():
        raise ValueError("Pinned local Omi C API runtime is unavailable")
    model_file = model / cpp_runtime.DEFAULT_GGUF_FILE
    expected_model_hash = runtime_config["artifacts"][cpp_runtime.DEFAULT_GGUF_FILE]
    if not model_file.is_file() or file_sha256(model_file) != expected_model_hash:
        raise ValueError("Pinned local Omi model digest mismatch")
    if importlib.metadata.version("omi-med-stt") != runtime_config["runtime_version"]:
        raise ValueError("Pinned Omi runtime version mismatch")
    source_code = {
        name: file_sha256(name)
        for name in (
            "services/audio_enhancement.py",
            "services/audio_enhancement_eval.py",
            "services/audio_provenance.py",
            "services/omi_adapter.py",
            "services/evaluation.py",
        )
    }

    conditions = [
        {
            "id": "source_unmodified",
            "enhancement_id": None,
            "transform": None,
            "parameters": None,
        },
        {
            "id": "rms_level_normalization_v1",
            "enhancement_id": "rms_level_normalization_v1",
            "transform": normalize_rms_transform(-23.0, 0.98),
            "parameters": {
                "target_rms_dbfs": -23.0,
                "peak_ceiling_fraction": 0.98,
                "algorithm": "whole_clip_rms_gain_with_peak_ceiling",
            },
        },
        {
            "id": "highpass_80hz_v1",
            "enhancement_id": "highpass_80hz_v1",
            "transform": highpass_transform(80, 4),
            "parameters": {
                "cutoff_hz": 80,
                "butterworth_order": 4,
                "implementation": "scipy_sosfiltfilt_zero_phase",
            },
        },
        {
            "id": "spectral_gate_percentile25_v1",
            "enhancement_id": "spectral_gate_percentile25_v1",
            "transform": spectral_gate_transform(25, 1.5, 0.15),
            "parameters": {
                "window": "hann",
                "nperseg": 512,
                "noverlap": 384,
                "noise_floor_percentile": 25,
                "threshold_multiplier": 1.5,
                "minimum_gain": 0.15,
                "algorithm": "whole_clip_percentile_spectral_gate",
            },
        },
    ]
    rows_by_condition = {condition["id"]: [] for condition in conditions}
    predictor = OmiPredictor(
        model,
        runtime_config["revision"],
        allow_empty_output=False,
    )
    try:
        for sample in manifest["samples"]:
            source = Path(audio_root) / sample["audio"]
            if file_sha256(source) != sample["audio_sha256"]:
                raise ValueError("Source audio does not match frozen manifest")
            for condition in conditions:
                candidate_record = None
                candidate_sha256 = sample["audio_sha256"]
                try:
                    if condition["enhancement_id"] is None:
                        candidate_path = source
                        candidate_sha256 = sample["audio_sha256"]
                    else:
                        with tempfile.TemporaryDirectory(
                            prefix="asr-enhancement-candidate-"
                        ) as temporary:
                            candidate_path = (
                                Path(temporary) / f"{sample['sample_id']}.wav"
                            )
                            candidate_record = prepare_candidate(
                                source,
                                candidate_path,
                                condition["enhancement_id"],
                                condition["transform"],
                                condition["parameters"],
                                {
                                    "kind": "same_sample_clock_filtering",
                                    "status": "sample_rate_and_frame_count_preserved",
                                    "input_sample_rate": 16000,
                                    "output_sample_rate": 16000,
                                    "maximum_mapping_error_ms": 1000 / 16000,
                                },
                            )
                            candidate_sha256 = candidate_record["candidate_sha256"]
                            started = time.perf_counter()
                            hypothesis = predictor(candidate_path)
                            elapsed = time.perf_counter() - started
                            scored = score(sample["reference"], hypothesis)
                            rows_by_condition[condition["id"]].append(
                                {
                                    "sample_id": sample["sample_id"],
                                    "group_id": sample["group_id"],
                                    "status": "completed",
                                    "error_code": None,
                                    "elapsed_seconds": round(elapsed, 4),
                                    "candidate_audio_sha256": candidate_sha256,
                                    "audio_provenance": candidate_record[
                                        "audio_provenance"
                                    ],
                                    "reference": sample["reference"],
                                    "hypothesis": hypothesis,
                                    **scored,
                                }
                            )
                        continue

                    started = time.perf_counter()
                    hypothesis = predictor(candidate_path)
                    elapsed = time.perf_counter() - started
                    scored = score(sample["reference"], hypothesis)
                    rows_by_condition[condition["id"]].append(
                        {
                            "sample_id": sample["sample_id"],
                            "group_id": sample["group_id"],
                            "status": "completed",
                            "error_code": None,
                            "elapsed_seconds": round(elapsed, 4),
                            "candidate_audio_sha256": candidate_sha256,
                            "audio_provenance": None,
                            "reference": sample["reference"],
                            "hypothesis": hypothesis,
                            **scored,
                        }
                    )
                except Exception as exc:
                    rows_by_condition[condition["id"]].append(
                        {
                            "sample_id": sample["sample_id"],
                            "group_id": sample["group_id"],
                            "status": "failed",
                            "error_code": "local_candidate_inference_or_transform_failed",
                            "failure_type": type(exc).__name__,
                            "candidate_audio_sha256": candidate_sha256,
                            "reference": sample["reference"],
                            "hypothesis": "",
                            **score(sample["reference"], ""),
                        }
                    )
                print(
                    json.dumps(
                        {
                            "condition_id": condition["id"],
                            "sample_id": sample["sample_id"],
                            "status": rows_by_condition[condition["id"]][-1]["status"],
                        }
                    ),
                    flush=True,
                )
    finally:
        predictor.close()

    baseline_rows = rows_by_condition["source_unmodified"]
    conditions_report = []
    baseline_by_sample = {row["sample_id"]: row for row in baseline_rows}
    for condition in conditions:
        rows = rows_by_condition[condition["id"]]
        deltas = {"improved_samples": 0, "degraded_samples": 0, "unchanged_samples": 0}
        if condition["id"] != "source_unmodified":
            for row in rows:
                original = baseline_by_sample[row["sample_id"]]
                delta = row["normalized_edits"] - original["normalized_edits"]
                deltas[
                    "improved_samples"
                    if delta < 0
                    else "degraded_samples"
                    if delta > 0
                    else "unchanged_samples"
                ] += 1
            deltas["net_normalized_edit_change"] = sum(
                row["normalized_edits"]
                - baseline_by_sample[row["sample_id"]]["normalized_edits"]
                for row in rows
            )
        conditions_report.append(
            {
                "condition_id": condition["id"],
                "transform_parameters": condition["parameters"],
                "summary": _summary(rows),
                "paired_sample_changes": deltas,
                "samples": rows,
            }
        )
    report = {
        "schema_version": "paired_audio_enhancement_development_v1",
        "dataset_id": manifest["dataset_id"],
        "manifest_sha256": manifest_hash,
        "baseline_run_sha256": baseline_hash,
        "source_dataset_role": manifest["split_role"],
        "model": {
            "profile_id": runtime_config["profile_id"],
            "runtime": "omi-med-stt",
            "runtime_version": runtime_config["runtime_version"],
            "model_revision": runtime_config["revision"],
            "artifacts": runtime_config["artifacts"],
            "local_model_sha256": file_sha256(model_file),
            "runtime_configuration": runtime_config,
            "empty_output_policy": "empty_native_output_is_failure",
        },
        "source_code_sha256": source_code,
        "scoring_profile": baseline_run_data["scoring_profile"],
        "failure_policy": baseline_run_data["failure_policy"],
        "maximum_normalized_wer": PROJECT_MAX_NORMALIZED_WER,
        "conditions": conditions_report,
        "limitations": [
            "Six convenience-selected utterances from one public mock consultation; development screening only.",
            "References are upstream mock annotations and are not independently clinically adjudicated.",
            "RMS level normalization is not LUFS normalization.",
            "Spectral gate estimates its floor from the entire clip and may suppress speech.",
            "No enhancement condition is enabled in the production ASR route.",
        ],
        "clinical_acceptance": False,
    }
    atomic_json(output, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", default="evaluation/reports/audio-enhancement-paired-v1.json"
    )
    args = parser.parse_args()
    run(output_path=args.output)
