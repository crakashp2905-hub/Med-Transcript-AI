import pytest

from services.asr.admission import evaluate_candidate_admission


def _evidence():
    return {
        "reference_words": 1000,
        "normalized_edits": 49,
        "failed_samples": 0,
        "sample_count": 20,
        "source_timing_validated": True,
        "license_reviewed": True,
        "critical_safety_review": "passed",
        "matched_paired_evaluation": True,
        "all_frozen_cases_accounted": True,
        "fabricated_outcomes": 0,
    }


def test_candidate_admission_requires_every_gate_and_preserves_five_percent():
    result = evaluate_candidate_admission("candidate-a", _evidence())
    assert result["status"] == "admitted"
    assert result["promotion_allowed"]
    assert result["maximum_normalized_wer"] == 0.05
    assert result["clinical_approval"] == "not_established_by_asr_admission"


def test_exactly_five_percent_is_within_the_maximum_gate():
    evidence = _evidence()
    evidence["normalized_edits"] = 50
    assert evaluate_candidate_admission("candidate-a", evidence)["promotion_allowed"]


@pytest.mark.parametrize(
    ("key", "value", "reason"),
    [
        ("normalized_edits", 51, "normalized_wer_exceeds_admission_maximum"),
        ("failed_samples", 1, "processing_failures_present"),
        ("source_timing_validated", False, "source_timing_not_validated"),
        ("license_reviewed", False, "license_not_reviewed"),
        ("critical_safety_review", "missing", "critical_safety_review_not_passed"),
        ("matched_paired_evaluation", False, "matched_paired_evaluation_missing"),
        ("all_frozen_cases_accounted", False, "frozen_case_coverage_incomplete"),
        ("fabricated_outcomes", 1, "fabricated_outcomes_present_or_unmeasured"),
        ("fabricated_outcomes", None, "fabricated_outcomes_present_or_unmeasured"),
    ],
)
def test_any_missing_or_failed_gate_denies_promotion(key, value, reason):
    evidence = _evidence()
    evidence[key] = value
    result = evaluate_candidate_admission("candidate-a", evidence)
    assert not result["promotion_allowed"]
    assert reason in result["reasons"]


def test_malformed_or_non_failure_inclusive_denominators_rejected():
    evidence = _evidence()
    evidence["reference_words"] = 0
    with pytest.raises(ValueError, match="invalid_failure_inclusive_asr_denominator"):
        evaluate_candidate_admission("candidate-a", evidence)
