import base64
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mock_api_spec_matches_local_export_routes_and_limits_claims():
    spec = json.loads(
        (ROOT / "docs/integrations/mock-ehr-api-v1.json").read_text(encoding="utf-8")
    )
    assert set(spec["paths"]) == {
        "/v1/encounters/{eid}/exports",
        "/v1/encounters/{eid}/exports/{xid}",
    }
    assert "post" in spec["paths"]["/v1/encounters/{eid}/exports"]
    assert "get" in spec["paths"]["/v1/encounters/{eid}/exports/{xid}"]
    assert spec["components"]["schemas"]["ExportRequest"]["required"] == [
        "approval_id",
        "format",
    ]
    assert spec["components"]["schemas"]["ExportRequest"]["properties"]["format"][
        "enum"
    ] == ["markdown", "text", "json", "fhir"]
    assert spec["x-validation-boundary"]["ehr_write"] is False
    assert spec["x-validation-boundary"]["receiver_profile"] == "not validated"
    assert spec["x-validation-boundary"]["external_fhir_validator"] == "not run"
    routes = (ROOT / "services/review/routers/exports.py").read_text(encoding="utf-8")
    assert '@app.post("/v1/encounters/{eid}/exports"' in routes
    assert '@app.get("/v1/encounters/{eid}/exports/{xid}")' in routes


def test_synthetic_fhir_bundle_attachment_and_no_conformance_claim():
    bundle = json.loads(
        (ROOT / "evaluation/integrations/fhir-test-bundle-v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert bundle["_validationBoundary"]["fixtureOnly"] is True
    assert bundle["_validationBoundary"]["notAConformanceClaim"] is True
    resource = bundle["entry"][0]["resource"]
    assert resource["resourceType"] == "DocumentReference"
    assert resource["status"] == "current"
    assert resource["docStatus"] == "final"
    attachment = resource["content"][0]["attachment"]
    assert attachment["contentType"] == "application/json"
    payload = json.loads(base64.b64decode(attachment["data"], validate=True))
    assert payload["note"]["demo"] == "synthetic"
    assert payload["note"]["id"] == resource["id"]
    assert payload["approval"]["status"] == "approved"
    assert payload["approval"]["note_sha256"] == resource["identifier"][0]["value"]

    from services.review.presentation import fhir_document

    note = {
        "id": resource["id"],
        "encounter_id": resource["context"]["encounter"][0]["identifier"]["value"],
        "demo": "synthetic",
    }
    approval = {
        "status": "approved",
        "note_sha256": resource["identifier"][0]["value"],
        "approved_at": resource["date"],
    }
    generated = json.loads(fhir_document(note, approval))
    generated_data = generated["content"][0]["attachment"]["data"]
    assert json.loads(base64.b64decode(generated_data, validate=True)) == payload
    generated["content"][0]["attachment"]["data"] = attachment["data"]
    assert generated == resource
