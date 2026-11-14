from uuid import uuid4

from fastapi.testclient import TestClient

from services.api.contracts import Identity
from services.api.main import create_app


def _headers(token):
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid4())}


def _encounter_payload():
    return {
        "patient_reference_id": str(uuid4()),
        "patient_identifiers_confirmed": True,
        "synthetic_data": True,
    }


def test_admin_is_restricted_to_session_and_admin_routes(tmp_path):
    token = "a" * 40
    identity = Identity(
        tenant_id=uuid4(), clinician_id=uuid4(), user_id=uuid4(), role="administrator"
    )
    client = TestClient(create_app(str(tmp_path / "admin.sqlite3"), {token: identity}))

    assert client.get("/v1/session", headers=_headers(token)).status_code == 200
    response = client.post(
        "/v1/encounters", json=_encounter_payload(), headers=_headers(token)
    )
    assert response.status_code == 403
    assert response.json()["code"] == "administrator_scope_required"
    assert client.get("/v1/study-dashboard", headers=_headers(token)).status_code == 403


def test_scribe_can_prepare_but_cannot_approve_or_amend(tmp_path):
    token = "b" * 40
    identity = Identity(
        tenant_id=uuid4(),
        clinician_id=uuid4(),
        user_id=uuid4(),
        role="scribe",
    )
    client = TestClient(create_app(str(tmp_path / "scribe.sqlite3"), {token: identity}))
    created = client.post(
        "/v1/encounters", json=_encounter_payload(), headers=_headers(token)
    )
    assert created.status_code == 201
    encounter_id = created.json()["id"]
    approval = {
        "note_version_id": str(uuid4()),
        "expected_note_sha256": "a" * 64,
        "verification_report_id": str(uuid4()),
        "patient_identifiers_reconfirmed": True,
    }
    response = client.post(
        f"/v1/encounters/{encounter_id}/approvals",
        json=approval,
        headers=_headers(token),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "physician_approval_required"

    response = client.post(
        f"/v1/encounters/{encounter_id}/amendments",
        json={"approval_id": str(uuid4()), "reason": "Synthetic correction"},
        headers=_headers(token),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "physician_approval_required"


def test_physician_and_legacy_clinician_roles_remain_valid():
    for role in ("physician", "clinician"):
        identity = Identity(tenant_id=uuid4(), clinician_id=uuid4(), role=role)
        assert identity.role == role
        assert identity.actor_id == identity.clinician_id
