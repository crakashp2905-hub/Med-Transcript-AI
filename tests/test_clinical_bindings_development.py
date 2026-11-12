import json
from pathlib import Path
from services.clinical_evaluation import adversarial
from tests.test_foundation import setup, headers
from tests.test_review_workflow import prepare, draft


def test_frozen_binding_cases_catch_medication_and_negation_swaps_without_false_alarms():
    report = adversarial("evaluation/clinical-bindings-development-v1.json")
    assert report["confusion_matrix"] == {
        "true_positive": 6,
        "false_positive": 0,
        "true_negative": 6,
        "false_negative": 0,
    }


def test_http_note_verification_blocks_new_drug_binding_error(setup):
    client, path, _ = setup
    source = "Take aspirin 75 mg and amlodipine 5 mg daily."
    eid, tx, facts = prepare(client, path, source)
    assert len(facts) == 1
    facts[0]["text"] = "Take aspirin 5 mg and amlodipine 75 mg daily."
    facts[0]["clarification"] = (
        "Deliberate synthetic medication dose reassignment for verification test."
    )
    result = draft(client, eid, tx, facts)
    codes = {row["code"] for row in result["verification"]["findings"]}
    assert "medication_dose_assignment_disagreement" in codes
    assert result["verification"]["gate"] == "blocked"
