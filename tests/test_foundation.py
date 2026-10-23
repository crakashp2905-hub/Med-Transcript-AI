import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from services.api.main import Identity, create_app


@pytest.fixture
def setup(tmp_path):
    path = str(tmp_path / "test.sqlite3")
    tenant = uuid4()
    tokens = {
        "a" * 40: Identity(tenant_id=tenant, clinician_id=uuid4()),
        "b" * 40: Identity(tenant_id=uuid4(), clinician_id=uuid4()),
        "c" * 40: Identity(tenant_id=tenant, clinician_id=uuid4()),
    }
    return TestClient(create_app(path, tokens)), path, tokens


def headers(token="a" * 40):
    return {"Authorization": f"Bearer {token}"}


def payload():
    return {"patient_reference_id": str(uuid4()), "patient_identifiers_confirmed": True,
            "synthetic_data": True}


def create(client):
    response = client.post("/v1/encounters", json=payload(), headers=headers())
    assert response.status_code == 201
    return response.json()["id"]


def authorization():
    return {"scopes": ["recording", "local_processing"], "policy_version": "synthetic-v1",
            "method": "verbal_documented",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}


def test_authentication_required(setup):
    client, _, _ = setup
    for auth in ({}, headers("invalid")):
        assert client.post("/v1/encounters", json=payload(), headers=auth).status_code == 401


@pytest.mark.parametrize("token", ["b" * 40, "c" * 40])
def test_other_tenant_and_unassigned_clinician_cannot_access(setup, token):
    client, _, _ = setup
    resource = create(client)
    for suffix in ("", "/processing-permission"):
        assert client.get(f"/v1/encounters/{resource}{suffix}", headers=headers(token)).status_code == 404
    assert client.post(f"/v1/encounters/{resource}/authorizations",
                       json=authorization(), headers=headers(token)).status_code == 404


@pytest.mark.parametrize("field,value", [("synthetic_data", False), ("patient_identifiers_confirmed", False),
    ("language", "ta"), ("requested_inference_mode", "hybrid"), ("timezone", "unknown/invalid"),
    ("tenant_id", "client-controlled")])
def test_scope_and_patient_confirmation_fail_closed(setup, field, value):
    client, _, _ = setup
    body = payload()
    body[field] = value
    assert client.post("/v1/encounters", json=body, headers=headers()).status_code == 422


def test_authorization_withdrawal_and_audit_are_durable(setup):
    client, path, tokens = setup
    resource = create(client)
    route = f"/v1/encounters/{resource}"
    assert client.get(route + "/processing-permission", headers=headers()).json()["recording_authorized"] is False
    response = client.post(route + "/authorizations", json=authorization(), headers=headers())
    assert response.status_code == 201
    aid = response.json()["id"]
    flags = client.get(route + "/processing-permission", headers=headers()).json()
    assert flags["local_processing_authorized"] is True
    assert flags["external_text_processing_authorized"] is False
    assert flags["external_audio_processing_authorized"] is False
    assert flags["inference_enabled"] is False
    withdraw = route + f"/authorizations/{aid}/withdraw"
    first = client.post(withdraw, headers=headers()).json()
    assert client.post(withdraw, headers=headers()).json() == first
    restarted = TestClient(create_app(path, tokens))
    assert restarted.get(route, headers=headers()).status_code == 200
    assert restarted.get(route + "/processing-permission", headers=headers()).json()["local_processing_authorized"] is False
    with sqlite3.connect(path) as con:
        actions = [row[0] for row in con.execute("SELECT action FROM audit")]
    assert actions.count("authorization_withdrawn") == 1
    assert "authorization_recorded" in actions


def test_expired_authorization_is_ineffective(setup):
    client, path, _ = setup
    resource = create(client)
    route = f"/v1/encounters/{resource}"
    body = authorization()
    assert client.post(route + "/authorizations", json=body, headers=headers()).status_code == 201
    with sqlite3.connect(path) as con:
        import json
        body["expires_at"] = "2000-01-01T00:00:00+00:00"
        con.execute("UPDATE authorizations SET body=?", (json.dumps(body),))
    flags = client.get(route + "/processing-permission", headers=headers()).json()
    assert flags["local_processing_authorized"] is False


def test_expired_and_naive_authorization_rejected(setup):
    client, _, _ = setup
    resource = create(client)
    for expiry in ("2000-01-01T00:00:00+00:00", "2099-01-01T00:00:00"):
        body = authorization()
        body["expires_at"] = expiry
        assert client.post(f"/v1/encounters/{resource}/authorizations", json=body, headers=headers()).status_code == 422


def test_errors_do_not_echo_content_and_responses_disable_cache(setup):
    client, _, _ = setup
    response = client.post("/v1/encounters", json={"secret": "sensitive-patient-text"}, headers=headers())
    assert response.status_code == 422
    assert "sensitive-patient-text" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_authorization_cannot_be_withdrawn_through_different_encounter(setup):
    client, _, _ = setup
    first, second = create(client), create(client)
    aid = client.post(f"/v1/encounters/{first}/authorizations", json=authorization(), headers=headers()).json()["id"]
    assert client.post(f"/v1/encounters/{second}/authorizations/{aid}/withdraw", headers=headers()).status_code == 404


def test_startup_requires_credentials(tmp_path):
    with pytest.raises(ValueError):
        create_app(str(tmp_path / "empty.db"), {})
