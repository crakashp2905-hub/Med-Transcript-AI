"""Offline acceptance for first-run local synthetic workspace onboarding."""

from tests.test_foundation import headers, payload


def test_local_onboarding_needs_no_email_or_oauth_activation(environment):
    client = environment.client
    config = client.get("/v1/auth/config")
    assert config.status_code == 200
    assert config.json() == {
        "mode": "local",
        "google_enabled": False,
        "local_key_enabled": True,
        "provider_label": "Google",
    }
    assert client.get("/v1/auth/login").status_code == 404
    assert client.get("/v1/session").status_code == 401

    token = "a" * 40
    auth = headers(token)
    session = client.get("/v1/session", headers=auth)
    assert session.status_code == 200
    assert session.json()["role"] == "clinician"
    assert session.json()["data_mode"] == "synthetic_only"
    assert session.json()["clinical_models_enabled"] is False

    encounter = client.post("/v1/encounters", json=payload(), headers=headers(token))
    assert encounter.status_code == 201
    encounter_id = encounter.json()["id"]
    rows = client.get("/v1/encounters", headers=headers(token))
    assert rows.status_code == 200
    assert encounter_id in {row["id"] for row in rows.json()["items"]}
