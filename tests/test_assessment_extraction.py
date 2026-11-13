from uuid import uuid4

from services.review.clinical import extract
from services.review.models import Fact


def extract_facts(text):
    return extract(
        {
            "segments": [
                {
                    "segment_id": str(uuid4()),
                    "text": text,
                    "role": "clinician",
                }
            ]
        }
    )


def test_explicit_assessment_is_source_linked_and_not_model_generated():
    fact = extract_facts("Assessment: migraine.")[0]

    assert fact["category"] == "assessment"
    assert fact["section"] == "assessment"
    assert fact["assessment_status"] == "explicitly_said"
    assert fact["text"] == "Assessment: migraine."
    assert fact["evidence"]["quote"] == fact["text"]
    assert Fact.model_validate(fact).assessment_status == "explicitly_said"


def test_suspected_diagnosis_remains_suggested_and_uncertain():
    fact = extract_facts("Working diagnosis: possible migraine.")[0]

    assert fact["category"] == "assessment"
    assert fact["assessment_status"] == "suggested"
    assert fact["assertion"] == "uncertain"


def test_unlabeled_symptom_does_not_become_a_diagnosis():
    fact = extract_facts("Patient reports a headache.")[0]

    assert fact["category"] == "symptom"
    assert fact["assessment_status"] == "unknown"


def test_fact_ids_are_stable_for_the_same_source_spans():
    source = {
        "segments": [
            {
                "segment_id": str(uuid4()),
                "text": "No cough. Fever yesterday.",
                "role": "patient",
            }
        ]
    }

    first = extract(source)
    second = extract(source)

    assert [fact["fact_id"] for fact in first] == [fact["fact_id"] for fact in second]
    assert len({fact["fact_id"] for fact in first}) == len(first)
    assert all(fact["evidence"]["quote"] == fact["text"] for fact in first)
