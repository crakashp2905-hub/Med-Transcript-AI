import pytest

from services.asr.subgroup_metrics import build_subgroup_analysis


def test_subgroups_keep_failures_and_report_unlabeled_clinical_coverage():
    samples = [
        {
            "sample_id": "a",
            "group_id": "consult-1",
            "speaker_role": "patient",
            "noise_condition": "quiet",
            "reference_uncertain": False,
            "reference": "No allergy to amoxicillin",
            "clinical_terms": ["amoxicillin", "allergy"],
        },
        {
            "sample_id": "b",
            "group_id": "consult-2",
            "speaker_role": "doctor",
            "noise_condition": "traffic",
            "reference_uncertain": True,
            "reference": "Start 0.5 mg",
        },
    ]
    rows = [
        {"sample_id": "a", "status": "completed", "hypothesis": "No allergy"},
        {"sample_id": "b", "status": "failed", "hypothesis": "ignored output"},
    ]
    result = build_subgroup_analysis(samples, rows)
    assert result["by_dimension"]["consultation"]["consult-1"]["normalized_wer"] == 0.5
    assert result["by_dimension"]["speaker_role"]["doctor"]["failed_case_count"] == 1
    assert result["by_dimension"]["noise_condition"]["traffic"]["normalized_edits"] == 3
    assert result["by_dimension"]["uncertainty"]["uncertain"]["normalized_wer"] == 1
    assert result["clinical_term_analysis"]["coverage_fraction"] == 0.5
    assert (
        result["clinical_term_analysis"]["terms"]["amoxicillin"]["missed_occurrences"]
        == 1
    )


def test_subgroup_rejects_missing_or_duplicate_case_rows():
    with pytest.raises(ValueError, match="coverage_mismatch"):
        build_subgroup_analysis(
            [{"sample_id": "a", "group_id": "c", "reference": "word"}], []
        )
