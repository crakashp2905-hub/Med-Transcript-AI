import pytest

from services.asr.clinical_entities import (
    ClinicalEntity,
    compare_candidate_safety,
    extract_medication_entities,
)


def test_medication_strengths_bind_to_their_own_drugs():
    text = "Take aspirin 75 mg and amlodipine 5 mg daily."
    entities = extract_medication_entities(text)
    drugs = [entity for entity in entities if entity.kind == "drug_name"]
    strengths = [entity for entity in entities if entity.kind == "strength"]
    assert [(entity.text, entity.related_to) for entity in drugs] == [
        ("aspirin", "medication-0"),
        ("amlodipine", "medication-1"),
    ]
    assert [(entity.text, entity.related_to) for entity in strengths] == [
        ("75 mg", "medication-0"),
        ("5 mg", "medication-1"),
    ]
    assert all(entity.assertion == "affirmed" for entity in entities)
    assert all(text[e.start_char : e.end_char] == e.text for e in entities)


def test_negation_and_affirmation_are_kept_on_separate_clauses():
    entities = extract_medication_entities(
        "Patient denies taking aspirin 75 mg, but takes amlodipine 5 mg."
    )
    drugs = [entity for entity in entities if entity.kind == "drug_name"]
    assert [(entity.text, entity.assertion) for entity in drugs] == [
        ("aspirin", "negated"),
        ("amlodipine", "affirmed"),
    ]


def test_typed_span_rejects_inverted_offsets():
    with pytest.raises(ValueError, match="invalid_entity_span"):
        ClinicalEntity(kind="strength", text="5 mg", start_char=5, end_char=4)


def test_candidate_comparison_blocks_negation_scope_and_drug_dose_swaps():
    negation = compare_candidate_safety("No fever but cough.", "Fever but no cough.")
    assert "negation_scope_disagreement" in negation["risk_reasons"]
    assert negation["review_required"] is True
    doses = compare_candidate_safety(
        "Take aspirin 75 mg and amlodipine 5 mg daily.",
        "Take aspirin 5 mg and amlodipine 75 mg daily.",
    )
    assert "medication_dose_assignment_disagreement" in doses["risk_reasons"]
    assert doses["automatic_adoption"] is False
    assert doses["clinical_truth_verified"] is False


def test_candidate_agreement_does_not_claim_truth_or_adopt():
    result = compare_candidate_safety("No fever.", "No fever.")
    assert result["review_required"] is False
    assert result["clinical_truth_verified"] is False
    assert result["automatic_adoption"] is False
