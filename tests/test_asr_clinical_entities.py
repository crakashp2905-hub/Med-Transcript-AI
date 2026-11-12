import pytest

from services.asr.clinical_entities import ClinicalEntity, extract_medication_entities


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
