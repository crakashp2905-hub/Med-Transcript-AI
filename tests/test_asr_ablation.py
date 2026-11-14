import hashlib

import pytest

from services.asr.ablation import (
    ARM_COMPONENTS,
    REQUIRED_ABLATION_ARMS,
    summarize_matched_ablation,
)
from services.evaluation import score


COHORT = [
    {
        "group_id": "consultation-a-clean",
        "audio_sha256": "a" * 64,
        "reference": "no fever today",
        "condition": "clean",
        "foreground_id": "consultation-a",
        "donor_id": None,
    },
    {
        "group_id": "consultation-a-distracted",
        "audio_sha256": "b" * 64,
        "reference": "warfarin 2.5 mg daily",
        "condition": "distracted",
        "foreground_id": "consultation-a",
        "donor_id": "consultation-b",
    },
]


def _row(case, hypothesis, failed=False):
    reference_sha = hashlib.sha256(case["reference"].encode("utf-8")).hexdigest()
    result = score(case["reference"], hypothesis)
    return {
        "group_id": case["group_id"],
        "audio_sha256": case["audio_sha256"],
        "reference_sha256": reference_sha,
        "condition": case["condition"],
        "foreground_id": case["foreground_id"],
        "donor_id": case["donor_id"],
        "hypothesis": hypothesis,
        "failed": failed,
        "reference_words": result["reference_words"],
        "normalized_edits": result["normalized_edits"],
    }


def _arms():
    return [
        {
            "arm_id": arm_id,
            "configuration": {
                "candidate": arm_id,
                "revision": "pinned",
                "base_model_sha256": "d" * 64,
                "changed_components": list(ARM_COMPONENTS[arm_id]),
                "compute_budget_seconds": 3600,
            },
            "training_group_ids": ["training-consultation"],
            "cases": [
                _row(COHORT[0], "no fever today"),
                _row(COHORT[1], "", failed=True),
            ],
        }
        for arm_id in sorted(REQUIRED_ABLATION_ARMS)
    ]


def test_matched_ablation_reconciles_cohort_and_counts_failures_as_deletions():
    report = summarize_matched_ablation(COHORT, _arms())

    assert report["sample_count"] == 2
    assert report["input_equivalence"] == (
        "all_six_arms_same_audio_reference_and_case_ids"
    )
    assert report["failure_policy"] == (
        "failed_case_empty_hypothesis_full_reference_deletions"
    )
    assert report["training_group_overlap"] == "none_detected"
    assert report["base_model_sha256"] == "d" * 64
    assert report["compute_budget_seconds"] == 3600
    assert set(report["arms"]) == REQUIRED_ABLATION_ARMS
    assert all(
        arm["sample_count"] == 2
        and arm["failed_samples"] == 1
        and arm["reference_words"] == 7
        and arm["normalized_edits"] == 4
        and arm["normalized_wer"] == pytest.approx(4 / 7)
        and arm["wer_admission"] == "fail"
        for arm in report["arms"].values()
    )


def test_matched_ablation_rejects_changed_inputs_missing_cases_and_leakage():
    changed = _arms()
    changed[0]["cases"][0]["audio_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="matched_ablation_input_mismatch"):
        summarize_matched_ablation(COHORT, changed)

    missing = _arms()
    missing[0]["cases"].pop()
    with pytest.raises(ValueError, match="matched_ablation_case_coverage_mismatch"):
        summarize_matched_ablation(COHORT, missing)

    leaked = _arms()
    leaked[0]["training_group_ids"] = ["consultation-b"]
    for arm in leaked[1:]:
        arm["training_group_ids"] = ["consultation-b"]
    with pytest.raises(ValueError, match="training_evaluation_group_leakage"):
        summarize_matched_ablation(COHORT, leaked)


def test_matched_ablation_rejects_failed_hypothesis_and_training_cohort_changes():
    nonempty_failure = _arms()
    nonempty_failure[0]["cases"][1]["hypothesis"] = "warfarin 2.5 mg daily"
    nonempty_failure[0]["cases"][1]["normalized_edits"] = 0
    with pytest.raises(ValueError, match="failed_case_must_score_as_full_deletion"):
        summarize_matched_ablation(COHORT, nonempty_failure)

    changed_training = _arms()
    changed_training[0]["training_group_ids"] = ["other-training-group"]
    with pytest.raises(ValueError, match="training_cohort_changed_across_arms"):
        summarize_matched_ablation(COHORT, changed_training)


def test_matched_ablation_rejects_model_or_compute_budget_changes():
    changed_model = _arms()
    changed_model[0]["configuration"]["base_model_sha256"] = "e" * 64
    with pytest.raises(ValueError, match="base_model_changed_across_ablation_arms"):
        summarize_matched_ablation(COHORT, changed_model)

    changed_budget = _arms()
    changed_budget[0]["configuration"]["compute_budget_seconds"] = 1800
    with pytest.raises(ValueError, match="compute_budget_changed_across_arms"):
        summarize_matched_ablation(COHORT, changed_budget)
