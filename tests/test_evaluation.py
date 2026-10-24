import pytest

from services.evaluation import PROJECT_MAX_NORMALIZED_WER, tokens, distance, score, wer_gate, run


def test_scoring_preserves_clinically_material_tokens():
    assert tokens("No fever. Dose 0.5 mg.") == ["no", "fever", "dose", "0.5", "mg"]
    assert score("No fever. Dose 0.5 mg.", "Fever. Dose 5 mcg.")["normalized_edits"] == 3


def test_failed_sample_empty_hypothesis_counts_all_reference_deletions():
    metrics = score("Patient denies drug allergies", "")
    assert metrics["reference_words"] == metrics["normalized_edits"] == 4
    assert distance([], ["hallucinated", "speech"]) == 2


def test_strict_three_percent_gate_uses_unrounded_counts():
    assert wer_gate({"reference_words": 100, "normalized_edits": 3, "failed_samples": 0}, 0.03)["status"] == "pass"
    gate = wer_gate({"reference_words": 9999, "normalized_edits": 300, "failed_samples": 0}, 0.03)
    assert gate["status"] == "fail"  # 3.0003% must not round down to an accepted 3%.
    assert "normalized_wer_exceeds_maximum" in gate["reasons"]


def test_low_average_does_not_hide_processing_failure_or_empty_denominator():
    assert wer_gate({"reference_words": 1000, "normalized_edits": 1, "failed_samples": 1}, 0.03)["status"] == "fail"
    assert wer_gate({"reference_words": 0, "normalized_edits": 0, "failed_samples": 0}, 0.03)["status"] == "fail"


@pytest.mark.parametrize("maximum", [float("nan"), float("inf"), -0.01, 1.01, True])
def test_invalid_wer_threshold_is_rejected(maximum):
    with pytest.raises(ValueError):
        wer_gate({"reference_words": 100, "normalized_edits": 0, "failed_samples": 0}, maximum)


def test_project_threshold_cannot_be_loosened_before_inference():
    with pytest.raises(ValueError, match="above 5%"):
        run("unused", None, "unused", max_normalized_wer=0.06)


def test_revised_five_percent_policy_preserves_exact_boundary():
    assert PROJECT_MAX_NORMALIZED_WER == .05
    assert wer_gate({"reference_words": 100, "normalized_edits": 5, "failed_samples": 0}, .05)["status"] == "pass"
    assert wer_gate({"reference_words": 9999, "normalized_edits": 500, "failed_samples": 0}, .05)["status"] == "fail"
    assert wer_gate({"reference_words": 100, "normalized_edits": 5, "failed_samples": 1}, .05)["status"] == "fail"
