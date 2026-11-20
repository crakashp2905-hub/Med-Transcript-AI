"""Group-cross-fit calibration of a local ASR one-best decoder score."""

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
from pathlib import Path

import numpy as np

from services.api.ingest import file_sha256, inspect_pcm_wav
from services.asr.adapter import ASRFailure, FasterWhisperAdapter
from services.asr.profiles import load_profiles
from services.evaluation import score
from services.immutable_reports import publish_json_once


SPLIT_PATH = Path("evaluation/runs/asr-training-splits/group-split-v1.json")
PROFILE_PATH = Path("evaluation/expanded-whisper-profiles.json")
PROFILE_ID = "tiny-en-smoke-v1"
OUTPUT_PATH = Path("evaluation/runs/asr-confidence-calibration-v1/report.json")
ALLOWED_SOURCES = {
    "primock57-expanded-v1",
    "primock57-validation-v1",
    "primock57-smoke-v1",
}
BOOTSTRAP_SEED = 20261121
BOOTSTRAP_ITERATIONS = 5000
SELECTION_THRESHOLD = 0.8


def _sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _source_commit():
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()


def _development_rows(split, dataset_root):
    if (
        split.get("schema_version") != "asr_original_consultation_group_split_v1"
        or split.get("complete") is not True
        or split.get("acceptance_labels_accessed") is not False
    ):
        raise ValueError("verified_group_split_required")
    assignments = split["group_assignments"]
    development = set(assignments["development"])
    reserved = set(assignments["reserved_acceptance"])
    selected = [
        row
        for row in split["rows"]
        if row["split"] == "development" and row["source_dataset"] in ALLOWED_SOURCES
    ]
    if not selected or any(
        set(row["contributing_group_ids"]) & reserved for row in selected
    ):
        raise ValueError("reserved_or_empty_calibration_development_set")
    if any(
        group not in development
        for row in selected
        for group in row["contributing_group_ids"]
    ):
        raise ValueError("calibration_group_split_mismatch")

    manifests = {}
    sources = {}
    for name in sorted(ALLOWED_SOURCES):
        manifest_path = Path(dataset_root) / name / "manifest.json"
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        if (
            manifest.get("rights_reviewed") is not True
            or manifest.get("data_class") != "approved_public"
        ):
            raise ValueError("rights_reviewed_public_manifest_required")
        sources[name] = {
            "manifest_path": manifest_path.as_posix(),
            "manifest_sha256": _sha_bytes(manifest_bytes),
            "license_id": manifest.get("license_id"),
        }
        manifests[name] = {
            row["sample_id"]: row
            for row in manifest.get("samples", [])
            if isinstance(row.get("sample_id"), str)
        }

    prepared = []
    seen = set()
    for row in selected:
        sample_id = row["sample_id"]
        if sample_id in seen:
            raise ValueError("duplicate_calibration_sample_id")
        seen.add(sample_id)
        source = manifests[row["source_dataset"]].get(sample_id)
        if source is None:
            raise ValueError("split_sample_missing_from_source_manifest")
        reference = source.get("reference")
        if (
            not isinstance(reference, str)
            or _sha_bytes(reference.encode()) != row["reference_sha256"]
        ):
            raise ValueError("calibration_reference_hash_mismatch")
        audio = Path(row["source_audio_path"])
        if not audio.is_file() or audio.is_symlink():
            raise ValueError("local_calibration_audio_required")
        if file_sha256(audio) != row["audio_sha256"]:
            raise ValueError("calibration_audio_hash_mismatch")
        prepared.append(
            {
                "sample_id": sample_id,
                "group_id": row["consultation_group_id"],
                "contributing_group_ids": row["contributing_group_ids"],
                "source_dataset": row["source_dataset"],
                "audio_path": audio,
                "audio_sha256": row["audio_sha256"],
                "reference_sha256": row["reference_sha256"],
                "reference": reference,
                "split": row["split"],
            }
        )
    return prepared, sources, sorted(development), sorted(reserved)


def _score_samples(prepared, profile):
    adapter = FasterWhisperAdapter(profile)
    rows = []
    for sample in prepared:
        try:
            metadata = inspect_pcm_wav(sample["audio_path"])
            metadata["sha256"] = sample["audio_sha256"]
            raw = adapter.transcribe(sample["audio_path"], metadata, lambda: None)
            segments = raw["segments"]
            hypothesis = " ".join(segment["text"].strip() for segment in segments)
            evidence = [
                segment["decoder_evidence"]
                for segment in segments
                if isinstance(segment.get("decoder_evidence"), dict)
            ]
            token_count = sum(len(item["token_ids"]) for item in evidence)
            mean_logprob = (
                sum(
                    item["average_logprob"] * len(item["token_ids"])
                    for item in evidence
                )
                / token_count
                if token_count
                else None
            )
            metrics = score(sample["reference"], hypothesis)
            status, error_code = "completed", None
        except ASRFailure as exc:
            segments, token_count, mean_logprob = [], 0, None
            metrics = score(sample["reference"], "")
            status, error_code = "failed", exc.code
        except Exception:
            segments, token_count, mean_logprob = [], 0, None
            metrics = score(sample["reference"], "")
            status, error_code = "failed", "calibration_sample_failed"
        reference_words = metrics["reference_words"]
        wer = metrics["normalized_edits"] / reference_words if reference_words else None
        rows.append(
            {
                "sample_id": sample["sample_id"],
                "consultation_group_id": sample["group_id"],
                "split": sample["split"],
                "source_dataset": sample["source_dataset"],
                "audio_sha256": sample["audio_sha256"],
                "reference_sha256": sample["reference_sha256"],
                "status": status,
                "error_code": error_code,
                "reference_words": reference_words,
                "normalized_edits": metrics["normalized_edits"],
                "normalized_wer": wer,
                "exact_match": bool(
                    status == "completed" and metrics["normalized_edits"] == 0
                ),
                "decoder_score_kind": "token_weighted_faster_whisper_best_sequence_average_logprob",
                "decoder_score": mean_logprob,
                "decoder_token_count": token_count,
                "decoder_segment_count": len(segments),
            }
        )
    return rows


def _crossfit(rows, groups):
    for held_out in groups:
        train = [
            row
            for row in rows
            if row["consultation_group_id"] != held_out
            and row["decoder_score"] is not None
        ]
        test = [
            row
            for row in rows
            if row["consultation_group_id"] == held_out
            and row["decoder_score"] is not None
        ]
        if not train:
            raise ValueError("empty_group_crossfit_training_fold")
        x_train = np.asarray([[row["decoder_score"]] for row in train])
        y_train = np.asarray([row["exact_match"] for row in train], dtype=int)
        prevalence = float(y_train.mean())
        if len(np.unique(y_train)) == 2:
            mean = float(x_train.mean())
            scale = float(x_train.std()) or 1.0
            normalized_train = (x_train - mean) / scale
            design_train = np.column_stack(
                (np.ones(len(normalized_train)), normalized_train[:, 0])
            )
            coefficients = np.zeros(2, dtype=np.float64)
            penalty = np.diag([0.0, 1.0])
            for _ in range(100):
                logits = np.clip(design_train @ coefficients, -30, 30)
                fitted = 1 / (1 + np.exp(-logits))
                gradient = (
                    design_train.T @ (fitted - y_train) / len(y_train)
                    + penalty @ coefficients
                )
                weights = fitted * (1 - fitted)
                hessian = (
                    design_train.T @ (design_train * weights[:, None]) / len(y_train)
                    + penalty
                    + np.eye(2) * 1e-8
                )
                step = np.linalg.solve(hessian, gradient)
                coefficients -= step
                if np.max(np.abs(step)) < 1e-8:
                    break
            normalized_test = np.asarray(
                [[row["decoder_score"]] for row in test], dtype=np.float64
            )
            design_test = np.column_stack(
                (
                    np.ones(len(normalized_test)),
                    ((normalized_test - mean) / scale)[:, 0],
                )
            )
            logits = np.clip(design_test @ coefficients, -30, 30)
            probabilities = 1 / (1 + np.exp(-logits))
            method = "logistic_platt_scaling"
        else:
            probabilities = np.full(len(test), prevalence)
            method = "training_fold_prevalence_fallback_single_class"
        for row, probability in zip(test, probabilities, strict=True):
            row["crossfit_probability_exact_match"] = float(probability)
            row["crossfit_training_groups"] = [
                group for group in groups if group != held_out
            ]
            row["crossfit_held_out_group"] = held_out
            row["crossfit_training_prevalence"] = prevalence
            row["crossfit_method"] = method
    for row in rows:
        if row["decoder_score"] is None:
            row.update(
                crossfit_probability_exact_match=None,
                crossfit_training_groups=[
                    group for group in groups if group != row["consultation_group_id"]
                ],
                crossfit_held_out_group=row["consultation_group_id"],
                crossfit_training_prevalence=None,
                crossfit_method="unscored_failure_review_required",
            )
    return rows


def _brier(rows):
    scored = [
        row for row in rows if row["crossfit_probability_exact_match"] is not None
    ]
    if not scored:
        return None
    return float(
        np.mean(
            [
                (row["crossfit_probability_exact_match"] - row["exact_match"]) ** 2
                for row in scored
            ]
        )
    )


def _selection(rows, threshold=SELECTION_THRESHOLD):
    scored = [
        row for row in rows if row["crossfit_probability_exact_match"] is not None
    ]
    selected = [
        row for row in scored if row["crossfit_probability_exact_match"] >= threshold
    ]
    return {
        "probability_threshold": threshold,
        "interpretation": "below_threshold_requires_review; exploratory_only",
        "scored_samples": len(scored),
        "selected_samples": len(selected),
        "coverage": len(selected) / len(scored) if scored else None,
        "exact_match_rate_among_selected": (
            sum(row["exact_match"] for row in selected) / len(selected)
            if selected
            else None
        ),
        "error_rate_among_selected": (
            sum(not row["exact_match"] for row in selected) / len(selected)
            if selected
            else None
        ),
    }


def _cluster_bootstrap(rows, groups):
    by_group = {
        group: [
            row
            for row in rows
            if row["consultation_group_id"] == group
            and row["crossfit_probability_exact_match"] is not None
        ]
        for group in groups
    }
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    values = {"brier": [], "coverage": [], "selected_error_rate": []}
    for _ in range(BOOTSTRAP_ITERATIONS):
        sampled = rng.choice(groups, size=len(groups), replace=True)
        bootstrap_rows = [row for group in sampled for row in by_group[group]]
        brier = _brier(bootstrap_rows)
        if brier is not None:
            values["brier"].append(brier)
        selection = _selection(bootstrap_rows)
        if selection["coverage"] is not None:
            values["coverage"].append(selection["coverage"])
        if selection["error_rate_among_selected"] is not None:
            values["selected_error_rate"].append(selection["error_rate_among_selected"])

    def interval(key):
        rows = values[key]
        return (
            [
                float(np.quantile(rows, 0.025)),
                float(np.quantile(rows, 0.975)),
            ]
            if rows
            else None
        )

    return {
        "method": "consultation_group_cluster_percentile_bootstrap",
        "seed": BOOTSTRAP_SEED,
        "iterations": BOOTSTRAP_ITERATIONS,
        "group_count": len(groups),
        "brier_95_percentile_interval": interval("brier"),
        "selection_coverage_95_percentile_interval": interval("coverage"),
        "selected_error_rate_95_percentile_interval": interval("selected_error_rate"),
    }


def build_calibration_report(
    split_path=SPLIT_PATH,
    profile_path=PROFILE_PATH,
    output_path=OUTPUT_PATH,
    dataset_root=Path("evaluation/datasets"),
):
    split_path, profile_path = Path(split_path), Path(profile_path)
    split_bytes = split_path.read_bytes()
    split = json.loads(split_bytes)
    prepared, source_manifests, all_development, reserved = _development_rows(
        split, dataset_root
    )
    groups = sorted({row["group_id"] for row in prepared})
    if len(groups) < 4 or not groups:
        raise ValueError("multiple_disjoint_development_groups_required")
    if set(groups) & set(reserved):
        raise ValueError("reserved_acceptance_calibration_group_forbidden")
    profiles = load_profiles(profile_path)
    profile = profiles.get(PROFILE_ID)
    if profile is None or profile.availability()["status"] != "available_not_admitted":
        raise ValueError("pinned_local_calibration_profile_unavailable")
    rows = _crossfit(_score_samples(prepared, profile), groups)
    scored_rows = [row for row in rows if row["decoder_score"] is not None]
    exact_count = sum(row["exact_match"] for row in scored_rows)
    base_rate = exact_count / len(scored_rows) if scored_rows else None
    report = {
        "schema_version": "asr_group_crossfit_confidence_calibration_v1",
        "complete": True,
        "clinical_acceptance": False,
        "automatic_promotion": False,
        "asr_model_fit": False,
        "calibrator_fit": True,
        "inference_executed": True,
        "source_commit": _source_commit(),
        "split_report_path": split_path.as_posix(),
        "split_report_sha256": _sha_bytes(split_bytes),
        "split_role": "public_development_only",
        "source_manifests": source_manifests,
        "profile": {
            key: value
            for key, value in profile.model_dump(mode="json").items()
            if key != "model_dir"
        },
        "profile_sha256": profile.sha256,
        "runtime_versions": {
            name: importlib.metadata.version(name)
            for name in (
                "faster-whisper",
                "ctranslate2",
                "tokenizers",
                "numpy",
            )
        },
        "group_protocol": {
            "method": "leave_one_development_consultation_group_out",
            "development_groups_available": all_development,
            "calibration_groups_used": groups,
            "fold_count": len(groups),
            "reserved_acceptance_groups_used": [],
            "training_samples_used_for_calibration": 0,
        },
        "score_definition": "token_weighted_mean_segment_average_logprob_from_faster_whisper_best_sequence",
        "calibration_target": "exact_normalized_utterance_match_to_public_mock_reference",
        "metrics": {
            "sample_count": len(rows),
            "scored_sample_count": len(scored_rows),
            "failed_sample_count": sum(row["status"] != "completed" for row in rows),
            "exact_match_count": exact_count,
            "exact_match_base_rate": base_rate,
            "out_of_fold_brier_score": _brier(rows),
            "out_of_fold_selection": _selection(rows),
            "uncertainty": _cluster_bootstrap(rows, groups),
            "wer_admission_maximum": 0.05,
            "wer_gate": "unchanged_and_not_evaluated_by_calibration",
        },
        "rows": rows,
        "limitations": [
            "This is an exploratory calibration of one-best decoder log probability on public mock utterances, not a backend-supported or clinically calibrated confidence score.",
            "Only eight consultation groups are present; group-bootstrap intervals are expected to be wide and do not establish external validity.",
            "Exact normalized transcript match is a research proxy; references are not clinician-adjudicated clinical gold.",
            "The 60 selected short utterances exclude full-length MedDistract audio and every reserved acceptance group.",
            "No candidate selection threshold was promoted or integrated into product routing; all existing baselines and the <=5% WER admission gate remain unchanged.",
        ],
    }
    published = publish_json_once(output_path, report)
    return published


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", type=Path, default=SPLIT_PATH)
    parser.add_argument("--profiles", type=Path, default=PROFILE_PATH)
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    report = build_calibration_report(args.split, args.profiles, args.out)
    print(
        json.dumps(
            {
                "output": args.out.as_posix(),
                "sample_count": report["metrics"]["sample_count"],
                "groups": report["group_protocol"]["fold_count"],
                "brier": report["metrics"]["out_of_fold_brier_score"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
