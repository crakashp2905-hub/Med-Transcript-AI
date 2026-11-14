import json
from uuid import uuid4

from fastapi.testclient import TestClient

from services.api.main import Identity, create_app
from services.api.storage import Store


def test_viewer_session_minimizes_identity_and_model_configuration(setup):
    _, path, tokens = setup
    clinician = tokens["a" * 40]
    viewer = TestClient(
        create_app(
            path,
            {
                "v" * 40: Identity(
                    tenant_id=clinician.tenant_id,
                    clinician_id=clinician.clinician_id,
                    role="viewer",
                )
            },
        )
    )
    response = viewer.get(
        "/v1/session", headers={"Authorization": "Bearer " + "v" * 40}
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "role": "viewer",
        "data_mode": "synthetic_only",
        "asr_profiles": [],
        "demo_available": False,
        "clinical_models_enabled": False,
    }
    assert "tenant_id" not in body and "clinician_id" not in body


def test_viewer_reads_only_synthetic_encounters(setup):
    clinician_client, path, tokens = setup
    clinician = tokens["a" * 40]
    synthetic_id, non_synthetic_id = str(uuid4()), str(uuid4())
    deletion_id = str(uuid4())
    with Store(path).transaction() as con:
        for encounter_id, synthetic in (
            (synthetic_id, True),
            (non_synthetic_id, False),
        ):
            con.execute(
                "INSERT INTO encounters(id,tenant,clinician,body,created_at) VALUES(?,?,?,?,?)",
                (
                    encounter_id,
                    str(clinician.tenant_id),
                    str(clinician.clinician_id),
                    json.dumps(
                        {
                            "patient_reference_id": str(uuid4()),
                            "synthetic_data": synthetic,
                        }
                    ),
                    "2026-11-14T00:00:00+00:00",
                ),
            )
        con.execute(
            "INSERT INTO deletion_requests(id,encounter,status,created_at,completed_at) VALUES(?,?,'pending',?,NULL)",
            (deletion_id, non_synthetic_id, "2026-11-14T00:00:00+00:00"),
        )
    viewer = TestClient(
        create_app(
            path,
            {
                "v" * 40: Identity(
                    tenant_id=clinician.tenant_id,
                    clinician_id=clinician.clinician_id,
                    role="viewer",
                )
            },
        )
    )
    headers = {"Authorization": "Bearer " + "v" * 40}
    result = viewer.get("/v1/encounters", headers=headers)
    assert result.status_code == 200
    assert [row["id"] for row in result.json()["items"]] == [synthetic_id]
    assert (
        viewer.get(f"/v1/encounters/{non_synthetic_id}", headers=headers).status_code
        == 404
    )
    assert (
        viewer.get(
            f"/v1/encounters/{non_synthetic_id}/workspace", headers=headers
        ).status_code
        == 404
    )
    assert (
        viewer.get(f"/v1/deletion-requests/{deletion_id}", headers=headers).status_code
        == 404
    )
    assert (
        viewer.get(f"/v1/encounters/{synthetic_id}", headers=headers).status_code == 200
    )
    assert (
        clinician_client.get(
            f"/v1/encounters/{non_synthetic_id}",
            headers={"Authorization": "Bearer " + "a" * 40},
        ).status_code
        == 200
    )
