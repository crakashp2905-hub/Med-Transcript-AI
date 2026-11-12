from typing import get_type_hints

from services.asr.clinical_entities import ClinicalEntity
from services.clinical_attribution import classify as classify_attribution
from services.evaluation_method import ClaimSignature
from services.review.clinical_models import SelectedFact
from services.review.models import ClinicalAssertion, Fact
from services.review.relationships import ClinicalRelationship
from services.uncertainty_classifier import classify as classify_uncertainty


ASSERTIONS = {"affirmed", "negated", "uncertain", "not_stated"}


def _enum_values(schema):
    if isinstance(schema, dict):
        if "enum" in schema:
            return set(schema["enum"])
        return set().union(*(_enum_values(value) for value in schema.values()))
    if isinstance(schema, list):
        return set().union(*(_enum_values(value) for value in schema))
    return set()


def test_serialized_clinical_schemas_preserve_all_assertion_states():
    for model in (Fact, SelectedFact, ClinicalEntity, ClinicalRelationship):
        assertion_schema = model.model_json_schema()["properties"]["assertion"]
        assert _enum_values(assertion_schema) == ASSERTIONS
    assert set(get_type_hints(ClaimSignature)["polarity"].__args__) == ASSERTIONS
    assert set(ClinicalAssertion.__args__) == ASSERTIONS


def test_unknown_subject_and_not_stated_assertion_remain_distinct():
    result = classify_uncertainty("")
    attribution = classify_attribution("")
    assert result == {
        "assertion": "not_stated",
        "value": None,
        "requires_review": True,
    }
    assert attribution["assertion"] == "not_stated"
    assert attribution["subject"] == "unknown"
    assert classify_uncertainty("Medication history not stated.")["assertion"] == (
        "not_stated"
    )
    assert classify_uncertainty("No fever.")["assertion"] == "negated"
    assert classify_uncertainty("Fever reported.")["assertion"] == "affirmed"
