"""Reconcile a matched VAD segmentation threshold ablation."""

import hashlib
import json
from pathlib import Path

from services.api.ingest import file_sha256
from services.asr.segmentation_candidate_runner import (
    ACTIVITY_PROFILE,
    MODE_CONFIGS,
    VAD_THRESHOLD_VARIANTS,
    _reference,
    _summarize,
    fast_score,
    validate_suite,
)
from services.immutable_reports import publish_json_once


def build_threshold_matrix(receipt_paths, output_path, *, suite_path):
    suite_path, suite, _, manifest = validate_suite(suite_path)
    suite_sha256 = file_sha256(suite_path)
    expected_manifest = {case["group_id"]: case for case in manifest["cases"]}
    expected_arm_ids = ("baseline", *VAD_THRESHOLD_VARIANTS)
    receipts = {}
    for raw_path in receipt_paths:
        path = Path(raw_path)
        report = json.loads(path.read_text(encoding="utf-8"))
        config = report.get("configuration", {})
        if config.get("mode") != "vad_cut_merge":
            raise ValueError("vad_threshold_receipt_mode_mismatch")
        arm_id = config.get("variant_id", "baseline")
        if arm_id not in expected_arm_ids or arm_id in receipts:
            raise ValueError("unknown_or_duplicate_vad_threshold_arm")
        receipts[arm_id] = (path, report)
    if set(receipts) != set(expected_arm_ids):
        raise ValueError("all_vad_threshold_receipts_required")

    expected_parameters = {"baseline": MODE_CONFIGS["vad_cut_merge"]}
    expected_parameters.update(VAD_THRESHOLD_VARIANTS)
    expected_profile_sha256 = next(
        row["source_profile_sha256"]
        for row in suite["jobs"]
        if row["candidate_id"] == "faster-whisper-tiny.en"
    )
    common_bindings = None
    source_commit = None
    baseline_cases = None
    arms = {}
    for arm_id in expected_arm_ids:
        path, report = receipts[arm_id]
        config = report.get("configuration", {})
        bindings = report.get("bindings", {})
        if (
            not report.get("complete")
            or report.get("schema_version") != "asr_segmentation_mode_receipt_v1"
            or config.get("mode_parameters") != expected_parameters[arm_id]
            or config.get("activity_profile") != ACTIVITY_PROFILE
            or config.get("activity_profile_sha256")
            != hashlib.sha256(
                json.dumps(
                    ACTIVITY_PROFILE, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            or config.get("profile_sha256") != expected_profile_sha256
            or (arm_id == "baseline" and "variant_id" in config)
            or (arm_id != "baseline" and config.get("variant_id") != arm_id)
        ):
            raise ValueError("vad_threshold_receipt_configuration_mismatch")
        if (
            bindings.get("suite_sha256") != suite_sha256
            or bindings.get("manifest_sha256") != suite["manifest_sha256"]
            or bindings.get("profile_sha256") != expected_profile_sha256
            or not isinstance(bindings.get("source_sha256"), dict)
            or not report.get("source_commit")
        ):
            raise ValueError("vad_threshold_receipt_source_mismatch")
        if common_bindings is None:
            common_bindings = bindings
            source_commit = report["source_commit"]
        elif bindings != common_bindings or report["source_commit"] != source_commit:
            raise ValueError("vad_threshold_receipt_source_commit_mismatch")

        rows = {row["group_id"]: row for row in report.get("cases", [])}
        if set(rows) != set(expected_manifest):
            raise ValueError("vad_threshold_cohort_mismatch")
        arm_cases = {}
        for group_id, source in expected_manifest.items():
            row = rows[group_id]
            reference = _reference(source)
            score = fast_score(reference, row.get("hypothesis", ""))
            if (
                row.get("audio_sha256") != source["audio_sha256"]
                or row.get("condition") != source["condition"]
                or row.get("foreground_id") != source["foreground_id"]
                or row.get("donor_id") != source.get("donor_id")
                or row.get("reference_sha256")
                != hashlib.sha256(reference.encode("utf-8")).hexdigest()
                or row.get("reference_words") != score["reference_words"]
                or row.get("normalized_edits") != score["normalized_edits"]
                or (row.get("failed") and row.get("hypothesis"))
            ):
                raise ValueError("vad_threshold_case_evidence_mismatch")
            arm_cases[group_id] = {
                "audio_sha256": row["audio_sha256"],
                "reference_sha256": row["reference_sha256"],
                "failed": row["failed"],
                "reference_words": score["reference_words"],
                "normalized_edits": score["normalized_edits"],
            }
        computed_summary = _summarize(list(rows.values()))
        if any(
            computed_summary[key] != report["summary"].get(key)
            for key in (
                "sample_count",
                "failed_samples",
                "reference_words",
                "normalized_edits",
                "normalized_wer",
                "wer_admission_maximum",
                "wer_admission",
                "wall_seconds",
            )
        ):
            raise ValueError("vad_threshold_summary_mismatch")
        if baseline_cases is None:
            baseline_cases = arm_cases
        elif any(
            (arm_cases[group_id][key] != baseline_cases[group_id][key])
            for group_id in baseline_cases
            for key in ("audio_sha256", "reference_sha256", "reference_words")
        ):
            raise ValueError("vad_threshold_case_hash_or_denominator_mismatch")

        arms[arm_id] = {
            "receipt_path": path.as_posix(),
            "receipt_sha256": file_sha256(path),
            "configuration": config,
            "summary": report["summary"],
            "resource_measurement": report["resource_measurement"],
            "cases": arm_cases,
        }

    if len(expected_manifest) != 16:
        raise ValueError("vad_threshold_requires_frozen_16_recording_cohort")
    result = {
        "schema_version": "asr_segmentation_threshold_matrix_v1",
        "complete": True,
        "clinical_acceptance": False,
        "automatic_promotion": False,
        "evaluation_source_commit": source_commit,
        "generator_source_sha256": file_sha256(Path(__file__)),
        "suite_sha256": suite_sha256,
        "manifest_sha256": suite["manifest_sha256"],
        "candidate_id": "faster-whisper-tiny.en",
        "profile_sha256": expected_profile_sha256,
        "activity_profile": ACTIVITY_PROFILE,
        "case_count": len(expected_manifest),
        "reference_words": sum(
            row["reference_words"] for row in baseline_cases.values()
        ),
        "input_hash_equivalence": "identical_audio_and_reference_hashes_for_every_case",
        "wer_admission_maximum": suite["maximum_normalized_wer"],
        "arms": arms,
        "limitations": [
            "Energy activity spans are uncalibrated heuristics, not annotated speech truth.",
            "All results are development-only and do not establish clinical acceptance.",
            "The 5% normalized-WER threshold is unchanged; no arm is promoted by this comparison.",
        ],
    }
    return publish_json_once(output_path, result)
