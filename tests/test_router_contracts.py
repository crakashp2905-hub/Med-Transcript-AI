from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from services.asr.profiles import canonical_json
from tests.test_foundation import headers


def contract_matches(actual, expected):
    if canonical_json(actual) != canonical_json(expected):
        raise ValueError("api_contract_changed")
    return True


def test_api_contract_survives_router_and_service_extraction(setup):
    client, _, _ = setup
    previous_path = Path("evaluation/contracts/api-v1-compatible-v8.json")
    successor = json.loads(
        Path("evaluation/contracts/api-v1-compatible-v9.json").read_text(
            encoding="utf-8"
        )
    )
    assert successor["supersedes"]["path"] == previous_path.as_posix()
    assert (
        successor["supersedes"]["sha256"]
        == hashlib.sha256(previous_path.read_bytes()).hexdigest()
    )
    assert successor["schema_version"] == "api_contract_successor_v9"
    expected = successor["contract"]
    verifier_limit = expected["components"]["schemas"]["VerifyRequest"]["properties"][
        "fact_ids"
    ]["anyOf"][0]
    assert verifier_limit["maxItems"] == 300
    actual = deepcopy(client.app.openapi())
    extension = actual["paths"].pop("/v1/encounters/{eid}/retranscriptions")
    schema = actual["components"]["schemas"].pop("RetranscribeRequest")
    assert "202" in extension["post"]["responses"]
    assert set(schema["required"]) == {
        "audio_asset_id",
        "transcript_version_id",
        "inference_profile_id",
        "start_ms",
        "end_ms",
    }
    assert contract_matches(actual, expected)
    mutated = deepcopy(expected)
    mutated["paths"].pop("/v1/encounters")
    with pytest.raises(ValueError):
        contract_matches(client.app.openapi(), mutated)


def test_dashboard_resolves_real_evidence_after_router_move(setup):
    client, _, _ = setup
    result = client.get("/v1/study-dashboard", headers=headers()).json()
    assert (
        result["sources"]["ranking"]["filename"]
        == "detailed-ranking-final-2026-10-29.json"
    )
    assert result["reports"]["ranking"]["complete"] is True
    assert result["clinical_validation"] is False


def test_review_state_errors_remain_sanitized_and_http_compatible():
    from services.review.service import ReviewStateError

    error = ReviewStateError(412, "version_changed_reload_required")
    assert (
        error.status_code == 412 and error.detail == "version_changed_reload_required"
    )
    with pytest.raises(ValueError):
        ReviewStateError(412, "Source text must not appear in error details.")


def test_all_routes_have_explicit_policies_and_new_unguarded_routes_fail(setup):
    from services.api.authorization_policy import validate

    client, _, _ = setup
    expected = json.loads(
        Path("evaluation/contracts/authorization-policy-v2.json").read_text()
    )
    provenance = json.loads(
        Path("evaluation/contracts/authorization-policy-v2.provenance.json").read_text()
    )
    assert (
        provenance["sha256"]
        == hashlib.sha256(
            Path("evaluation/contracts/authorization-policy-v2.json").read_bytes()
        ).hexdigest()
    )
    assert (
        provenance["supersedes"]["path"]
        == "evaluation/contracts/authorization-policy-v1.json"
    )
    coverage = validate(client.app, expected)
    assert coverage["routes_checked"] >= 60
    assert coverage["openapi_operations_checked"] == 60
    assert coverage["authenticated_operations_checked"] >= 50
    assert coverage["operation_schema_contracts_checked"] == 60
    assert coverage["path_parameters_checked"] > 0

    @client.app.get("/v1/unreviewed-test-route")
    def unreviewed():
        return {"unexpected": True}

    with pytest.raises(ValueError):
        validate(client.app, expected)


def test_all_identity_routes_reject_missing_auth_and_viewer_writes(setup):
    import re
    from uuid import uuid4
    from services.api.authorization_policy import inventory
    from services.api.main import create_app, Identity
    from fastapi.testclient import TestClient

    client, path, tokens = setup
    base = next(iter(tokens.values()))
    viewer = TestClient(
        create_app(
            path,
            {
                "v" * 40: Identity(
                    tenant_id=base.tenant_id,
                    clinician_id=base.clinician_id,
                    role="viewer",
                )
            },
        )
    )
    count = 0
    for row in inventory(client.app):
        if row["policy"] != "authenticated_scoped_identity":
            continue
        path = re.sub(r"\{[^}]+\}", str(uuid4()), row["path"])
        kwargs = {"json": {}} if row["method"] in ("POST", "PATCH", "PUT") else {}
        response = client.request(
            row["method"], path, headers={"Idempotency-Key": str(uuid4())}, **kwargs
        )
        assert response.status_code == 401, (row, response.status_code)
        if row["method"] not in ("GET", "HEAD", "OPTIONS"):
            response = viewer.request(
                row["method"],
                path,
                headers={
                    "Authorization": "Bearer " + "v" * 40,
                    "Idempotency-Key": str(uuid4()),
                },
                **kwargs,
            )
            assert response.status_code == 403, (row, response.status_code)
        count += 1
    assert count >= 50
