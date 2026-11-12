import pytest
import json
from pathlib import Path

from services.clinical_impact_triage import audit_saved_corpus, classify_edit, summarize


def test_medication_dose_negation_and_allergy_get_first_review_tier():
    row = classify_edit(
        {
            "operation": "substitution",
            "reference_token": "warfarin",
            "hypothesis_token": "aspirin",
        }
    )
    dose = classify_edit(
        {
            "operation": "deletion",
            "reference_token": "5mg",
            "hypothesis_token": None,
        }
    )
    negation = classify_edit(
        {
            "operation": "deletion",
            "reference_token": "denies",
            "hypothesis_token": None,
        }
    )
    allergy = classify_edit(
        {
            "operation": "substitution",
            "reference_token": "allergy",
            "hypothesis_token": "history",
        }
    )

    assert row["provisional_review_tier"] == dose["provisional_review_tier"] == 1
    assert negation["provisional_impact_categories"] == ["negation_or_assertion"]
    assert "allergy" in allergy["provisional_impact_categories"]
    assert all(
        not result["clinical_severity_validated"]
        for result in (row, dose, negation, allergy)
    )


def test_frequency_chronology_and_units_are_overlapping_second_tier_cues():
    frequency = classify_edit(
        {
            "operation": "substitution",
            "reference_token": "twice",
            "hypothesis_token": "once",
        }
    )
    chronology = classify_edit(
        {
            "operation": "substitution",
            "reference_token": "yesterday",
            "hypothesis_token": "today",
        }
    )
    unit = classify_edit(
        {"operation": "deletion", "reference_token": "mg", "hypothesis_token": None}
    )

    assert frequency["provisional_review_tier"] == 2
    assert chronology["provisional_review_tier"] == 2
    assert unit["provisional_review_tier"] == 2


def test_identity_requires_explicit_human_annotation_and_summaries_keep_overlap():
    lexical_only = classify_edit(
        {
            "operation": "substitution",
            "reference_token": "patient",
            "hypothesis_token": "doctor",
        }
    )
    annotated = classify_edit(
        {
            "operation": "substitution",
            "reference_token": "patient",
            "hypothesis_token": "doctor",
            "identity_attribution_error": True,
        }
    )
    summary = summarize([annotated])

    assert (
        "identity_or_speaker_attribution"
        not in lexical_only["provisional_impact_categories"]
    )
    assert (
        "identity_or_speaker_attribution" in annotated["provisional_impact_categories"]
    )
    assert summary["category_counts_overlap"] is True
    assert summary["category_counts"]["identity_or_speaker_attribution"] == 1
    assert summary["clinical_severity_validated"] is False
    assert summary["release_authorized"] is False


def test_saved_corpus_priority_report_replays_with_source_hashes():
    saved = json.loads(
        Path("evaluation/reports/clinical-impact-triage-v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert audit_saved_corpus() == saved
    assert saved["error_rows"] == 137356
    assert saved["category_counts"]["identity_or_speaker_attribution"] == 0
    assert saved["category_counts"]["dose_or_strength_value"] == 0
    assert saved["inference_calls"] == 0


@pytest.mark.parametrize("row", [None, [], {"reference_token": 42}])
def test_invalid_error_rows_fail_closed(row):
    with pytest.raises(ValueError):
        classify_edit(row)
