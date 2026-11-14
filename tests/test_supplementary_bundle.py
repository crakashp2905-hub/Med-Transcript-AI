import pytest

from services.supplementary_bundle import _sample_result, build


def test_supplement_is_sample_level_pseudonymous_and_failure_inclusive():
    result = build(".")
    assert result["dataset"]["sample_count"] == 118
    assert len(result["source_reports"]) == 7
    assert len(result["sample_results"]) == 118 * 7
    assert result["sample_results_csv"].count("\n") == 118 * 7 + 1
    assert result["failure_policy"] == "empty_hypothesis_full_reference_deletions"
    assert result["identifiers"]["transcript_text_included"] is False
    assert result["identifiers"]["original_sample_ids_included"] is False
    assert result["error_taxonomy"]["clinical_category_labels_available"] is False
    assert result["independent_clinical_gold"] is False
    assert all(
        row["sample_ref"].startswith("sample-") for row in result["sample_results"]
    )


def test_failed_sample_requires_full_reference_deletion_count():
    failed = {
        "candidate_id": "fixture",
        "status": "failed",
        "normalized_edits": 5,
        "reference_words": 5,
        "error_code": "fixture_failure",
    }
    assert _sample_result(failed, 1, 1, "clinician")["failed_sample"] is True
    failed["normalized_edits"] = 4
    with pytest.raises(ValueError, match="full_reference"):
        _sample_result(failed, 1, 1, "clinician")
