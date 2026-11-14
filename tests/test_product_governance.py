import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_commercial_support_security_and_launch_materials_keep_validation_boundaries():
    contract = json.loads(
        (ROOT / "evaluation/contracts/product-commercial-operations-v1.json").read_text(
            encoding="utf-8"
        )
    )
    document = (ROOT / contract["document"]).read_text(encoding="utf-8")
    assert contract["verified_task_ids"] == [f"MTA-15-{i:02d}" for i in range(21, 29)]
    assert contract["scenario_ids"] == [
        "individual_clinician",
        "small_clinic",
        "institution",
    ]
    assert len(contract["simulated_feedback_ids"]) == 5
    assert contract["market_size_claimed"] is False
    assert contract["paying_demand_claimed"] is False
    assert contract["ehr_certification_claimed"] is False
    assert contract["real_patient_release_authorized"] is False
    for section in (
        "## 21. Hypothetical business scenarios",
        "## 22. Release notes, change log, FAQ, and escalation",
        "## 23. FHIR R4 export boundary",
        "## 24. Buyer privacy and security checklist",
        "### Data-flow diagram",
        "### Operator responsibilities",
        "## 25. Investor demo deck outline",
        "## 26. Simulated feedback log and reprioritization rules",
        "## 27. Roadmap scorecard",
        "## 28. Launch decision policy",
    ):
        assert section in document
    assert "It cannot authorize real-patient processing" in document
    assert "submit a FHIR transaction" in document


def test_fhir_r4_serialization_keeps_approval_and_identifier_integrity():
    import base64
    from services.review.presentation import fhir_document

    note = {
        "id": "note-123",
        "encounter_id": "encounter-456",
        "facts": [
            {
                "fact_id": "fact-1",
                "statement": "Synthetic reviewed statement.",
                "evidence": [{"segment_id": "segment-1", "start_ms": 500, "end_ms": 900}],
            }
        ],
    }
    approval = {
        "id": "approval-789",
        "note_sha256": "a" * 64,
        "approved_at": "2026-11-14T00:00:00Z",
    }
    resource = json.loads(fhir_document(note, approval, {"case_id": "synthetic-1"}))
    assert resource["resourceType"] == "DocumentReference"
    assert resource["id"] == note["id"]
    assert resource["identifier"][0]["value"] == approval["note_sha256"]
    body = json.loads(base64.b64decode(resource["content"][0]["attachment"]["data"]))
    assert body["approval"]["id"] == approval["id"]
    assert body["note"]["encounter_id"] == note["encounter_id"]
    assert body["note"]["facts"] == note["facts"]
    assert body["source"]["case_id"] == "synthetic-1"
    assert resource["docStatus"] == "final"
