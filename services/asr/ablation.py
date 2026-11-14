"""Failure-inclusive matched-input validation for ASR ablation arms."""

import hashlib
import math

from services.canonical import content_sha256
from services.evaluation import score

REQUIRED_ABLATION_ARMS = frozenset(
    {
        "fixed_baseline",
        "vad_only",
        "decoder_only",
        "terminology_only",
        "repair_only",
        "full_pipeline",
    }
)
ARM_COMPONENTS = {
    "fixed_baseline": (),
    "vad_only": ("vad",),
    "decoder_only": ("decoder",),
    "terminology_only": ("terminology",),
    "repair_only": ("repair",),
    "full_pipeline": ("decoder", "repair", "terminology", "vad"),
}


def summarize_matched_ablation(cohort, arms):
    """Validate six arm reports against one frozen cohort and score failures as deletions.

    `cohort` is the manifest's case list. Each case provides group_id,
    audio_sha256, reference, condition, foreground_id, and optional donor_id.
    Each arm provides candidate_id, a frozen configuration, an explicit list of
    training_group_ids (empty when none are known/used), and one result per case.
    No transcript text is copied to the summary.
    """
    if not isinstance(cohort, list) or not cohort or not isinstance(arms, list):
        raise ValueError("matched_ablation_inputs_required")
    expected = {}
    for case in cohort:
        if not isinstance(case, dict):
            raise ValueError("invalid_matched_ablation_case")
        case_id = case.get("group_id")
        audio_sha = case.get("audio_sha256")
        reference = case.get("reference")
        if (
            not isinstance(case_id, str)
            or not case_id
            or not isinstance(audio_sha, str)
            or len(audio_sha) != 64
            or any(character not in "0123456789abcdef" for character in audio_sha)
            or not isinstance(reference, str)
            or not isinstance(case.get("condition"), str)
            or not isinstance(case.get("foreground_id"), str)
        ):
            raise ValueError("invalid_matched_ablation_case")
        if case_id in expected:
            raise ValueError("duplicate_matched_ablation_case")
        expected[case_id] = {
            "audio_sha256": audio_sha,
            "reference_sha256": hashlib.sha256(reference.encode("utf-8")).hexdigest(),
            "reference": reference,
            "condition": case["condition"],
            "foreground_id": case["foreground_id"],
            "donor_id": case.get("donor_id"),
        }

    rows_by_arm = {}
    train_groups_by_arm = {}
    config_digests = {}
    base_model_digests = set()
    compute_budgets = set()
    arm_wall_seconds = {}
    for arm in arms:
        if not isinstance(arm, dict):
            raise ValueError("invalid_matched_ablation_arm")
        arm_id = arm.get("arm_id")
        configuration = arm.get("configuration")
        train_groups = arm.get("training_group_ids")
        rows = arm.get("cases")
        if (
            arm_id not in REQUIRED_ABLATION_ARMS
            or arm_id in rows_by_arm
            or not isinstance(configuration, dict)
            or not isinstance(train_groups, list)
            or any(not isinstance(group, str) or not group for group in train_groups)
            or len(train_groups) != len(set(train_groups))
            or not isinstance(rows, list)
        ):
            raise ValueError("invalid_or_duplicate_matched_ablation_arm")
        base_model_sha = configuration.get("base_model_sha256")
        components = configuration.get("changed_components")
        compute_budget = configuration.get("compute_budget_seconds")
        if (
            not isinstance(base_model_sha, str)
            or len(base_model_sha) != 64
            or any(character not in "0123456789abcdef" for character in base_model_sha)
            or not isinstance(components, list)
            or any(not isinstance(component, str) for component in components)
            or len(components) != len(set(components))
            or tuple(sorted(components)) != ARM_COMPONENTS[arm_id]
            or type(compute_budget) is not int
            or compute_budget <= 0
        ):
            raise ValueError("invalid_matched_ablation_configuration")
        base_model_digests.add(base_model_sha)
        compute_budgets.add(compute_budget)
        wall_seconds = arm.get("wall_seconds")
        if (
            not isinstance(wall_seconds, (int, float))
            or isinstance(wall_seconds, bool)
            or not math.isfinite(wall_seconds)
            or wall_seconds <= 0
            or wall_seconds > compute_budget
        ):
            raise ValueError("ablation_arm_wall_time_outside_common_budget")
        arm_wall_seconds[arm_id] = float(wall_seconds)
        rows_by_arm[arm_id] = rows
        train_groups_by_arm[arm_id] = frozenset(train_groups)
        config_digests[arm_id] = content_sha256(configuration)

    if set(rows_by_arm) != REQUIRED_ABLATION_ARMS:
        raise ValueError("complete_six_arm_matrix_required")
    training_cohorts = set(train_groups_by_arm.values())
    if len(training_cohorts) != 1:
        raise ValueError("training_cohort_changed_across_arms")
    if len(base_model_digests) != 1:
        raise ValueError("base_model_changed_across_ablation_arms")
    if len(compute_budgets) != 1:
        raise ValueError("compute_budget_changed_across_arms")
    evaluation_groups = {
        group
        for case in expected.values()
        for group in (case["foreground_id"], case["donor_id"])
        if group is not None
    }
    if training_cohorts.pop() & evaluation_groups:
        raise ValueError("training_evaluation_group_leakage")

    expected_ids = set(expected)
    summaries = {}
    for arm_id, rows in rows_by_arm.items():
        by_id = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("invalid_matched_ablation_result")
            case_id = row.get("group_id")
            if case_id not in expected or case_id in by_id:
                raise ValueError("unknown_or_duplicate_matched_ablation_result")
            by_id[case_id] = row
        if set(by_id) != expected_ids:
            raise ValueError("matched_ablation_case_coverage_mismatch")

        edits = words = failures = 0
        for case_id, frozen in expected.items():
            row = by_id[case_id]
            if (
                row.get("audio_sha256") != frozen["audio_sha256"]
                or row.get("reference_sha256") != frozen["reference_sha256"]
                or row.get("condition") != frozen["condition"]
                or row.get("foreground_id") != frozen["foreground_id"]
                or row.get("donor_id") != frozen["donor_id"]
            ):
                raise ValueError("matched_ablation_input_mismatch")
            failed = row.get("failed")
            hypothesis = row.get("hypothesis")
            if type(failed) is not bool or not isinstance(hypothesis, str):
                raise ValueError("invalid_failure_inclusive_result")
            if failed and hypothesis:
                raise ValueError("failed_case_must_score_as_full_deletion")
            scored = score(frozen["reference"], hypothesis)
            if (
                type(row.get("reference_words")) is not int
                or type(row.get("normalized_edits")) is not int
                or row.get("reference_words") != scored["reference_words"]
                or row.get("normalized_edits") != scored["normalized_edits"]
            ):
                raise ValueError("matched_ablation_score_mismatch")
            words += scored["reference_words"]
            edits += scored["normalized_edits"]
            failures += int(failed)
        summaries[arm_id] = {
            "configuration_sha256": config_digests[arm_id],
            "wall_seconds": arm_wall_seconds[arm_id],
            "sample_count": len(by_id),
            "failed_samples": failures,
            "reference_words": words,
            "normalized_edits": edits,
            "normalized_wer": edits / words if words else None,
            "wer_admission_maximum": 0.05,
            "wer_admission": "pass" if words and edits / words <= 0.05 else "fail",
        }

    cohort_digest = content_sha256(
        [
            {
                "group_id": case_id,
                "audio_sha256": case["audio_sha256"],
                "reference_sha256": case["reference_sha256"],
                "condition": case["condition"],
                "foreground_id": case["foreground_id"],
                "donor_id": case["donor_id"],
            }
            for case_id, case in sorted(expected.items())
        ]
    )
    return {
        "schema_version": "matched_asr_ablation_v1",
        "cohort_sha256": cohort_digest,
        "sample_count": len(expected),
        "input_equivalence": "all_six_arms_same_audio_reference_and_case_ids",
        "failure_policy": "failed_case_empty_hypothesis_full_reference_deletions",
        "training_group_overlap": "none_detected_in_declared_project_training_groups",
        "upstream_pretraining_overlap": "not_audited",
        "base_model_sha256": next(iter(base_model_digests)),
        "compute_budget_seconds": next(iter(compute_budgets)),
        "arms": summaries,
        "clinical_adjudication": "not_established_by_automated_metrics",
    }
