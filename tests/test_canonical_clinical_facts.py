from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.review.models import DraftInput, Fact


def source_fact(text="Cough", **attributes):
    segment_id = uuid4()
    fact_id = attributes.pop("fact_id", uuid4())
    return Fact(
        fact_id=fact_id,
        text=text,
        evidence={
            "segment_id": segment_id,
            "start_char": 0,
            "end_char": len(text),
            "quote": text,
        },
        **attributes,
    )


def test_canonical_fact_has_explicit_clinical_source_state_and_review_status():
    fact = source_fact()
    assert fact.assertion == "uncertain"
    assert fact.uncertainty == "unknown"
    assert fact.temporality == "unknown"
    assert fact.action == "unknown"
    assert fact.relations == []
    assert fact.evidence is not None
    assert fact.source_modality == "transcript"
    assert fact.review_status == "unreviewed"


def test_canonical_fact_tracks_action_uncertainty_relations_and_review_state():
    medication = source_fact("Started amoxicillin")
    symptom = source_fact(
        "Cough",
        relations=[
            {"related_fact_id": medication.fact_id, "relation_type": "temporality"}
        ],
    )
    medication.action = "start"
    medication.uncertainty = "certain"
    medication.reviewed = True
    medication.critical_reviewed = True
    medication.review_status = "critical_reviewed"

    draft = DraftInput(transcript_version_id=uuid4(), facts=[symptom, medication])
    assert draft.facts[0].relations[0].related_fact_id == medication.fact_id
    assert draft.facts[1].action == "start"
    assert draft.facts[1].uncertainty == "certain"
    assert draft.facts[1].review_status == "critical_reviewed"


@pytest.mark.parametrize("relation_target", ["self", "unknown"])
def test_fact_relation_cannot_point_to_self_or_missing_fact(relation_target):
    fact_id = uuid4()
    target_id = fact_id if relation_target == "self" else uuid4()
    fact = source_fact(
        fact_id=fact_id,
        relations=[{"related_fact_id": target_id, "relation_type": "dose"}],
    )
    with pytest.raises(ValidationError, match="fact_relation_target_invalid"):
        DraftInput(transcript_version_id=uuid4(), facts=[fact])


def test_fact_review_status_must_match_individual_review_flags():
    fact = source_fact().model_dump()
    fact["review_status"] = "reviewed"

    with pytest.raises(ValidationError, match="review_status_must_match_review_flags"):
        Fact.model_validate(fact)
