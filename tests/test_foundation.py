import sqlite3
import hashlib
import io
import json
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from services.api.main import Identity, create_app
from services.api.ingest import inspect_pcm_wav, run_once
from services.api.storage import MIGRATIONS, Store


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
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid4())}


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


def wav_bytes():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(b"\0\0" * 1600)
    return buffer.getvalue()


def upload_session(client, resource, content):
    route = f"/v1/encounters/{resource}"
    response = client.post(route + "/authorizations", json=authorization(), headers=headers())
    assert response.status_code == 201
    aid = response.json()["id"]
    created = client.post(route + "/audio-uploads", json={"bytes": len(content),
                          "sha256": hashlib.sha256(content).hexdigest()}, headers=headers())
    assert created.status_code == 201
    return created.json(), aid


def queue_upload(client, content=None):
    resource = create(client)
    content = wav_bytes() if content is None else content
    upload, aid = upload_session(client, resource, content)
    response = client.put(upload["content_url"], content=content,
                          headers={**headers(), "Content-Type": "audio/wav"})
    assert response.status_code == 200
    route = f"/v1/encounters/{resource}/audio-uploads/{upload['id']}/complete"
    queued = client.post(route, headers=headers())
    assert queued.status_code == 202
    return resource, upload, aid, queued.json()


def test_idempotency_retry_conflict_and_restart(setup):
    client, path, tokens = setup
    body, auth = payload(), headers()
    first = client.post("/v1/encounters", json=body, headers=auth)
    assert first.status_code == 201
    restarted = TestClient(create_app(path, tokens))
    assert restarted.post("/v1/encounters", json=body, headers=auth).json() == first.json()
    changed = {**body, "patient_reference_id": str(uuid4())}
    assert restarted.post("/v1/encounters", json=changed, headers=auth).status_code == 409
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM encounters").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM audit WHERE action='encounter_created'").fetchone()[0] == 1


def test_concurrent_encounter_retry_creates_one_record(setup):
    _, path, tokens = setup
    body, auth = payload(), headers()
    def request(_):
        with TestClient(create_app(path, tokens)) as client:
            return client.post("/v1/encounters", json=body, headers=auth)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(request, range(4)))
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 1


def test_idempotency_is_actor_scoped_and_required(setup):
    client, _, _ = setup
    body, auth = payload(), headers()
    first = client.post("/v1/encounters", json=body, headers=auth).json()
    other = {**auth, "Authorization": "Bearer " + "b" * 40}
    second = client.post("/v1/encounters", json=body, headers=other).json()
    assert first["id"] != second["id"]
    assert client.post("/v1/encounters", json=body, headers={"Authorization": auth["Authorization"]}).status_code == 422


def test_legacy_database_migrates_without_losing_encounters(tmp_path):
    path = str(tmp_path / "legacy.sqlite3")
    with sqlite3.connect(path) as con:
        con.executescript(MIGRATIONS[0])
        con.execute("INSERT INTO encounters VALUES (?,?,?,?,?)", ("legacy", "t", "c", "{}", "2026-01-01"))
    Store(path)
    Store(path)  # Migration is repeatable at application startup.
    with sqlite3.connect(path) as con:
        assert con.execute("PRAGMA user_version").fetchone()[0] == 2
        assert con.execute("SELECT id FROM encounters").fetchone()[0] == "legacy"


def test_upload_ingest_end_to_end_and_duplicate_completion(setup):
    client, path, tokens = setup
    resource, upload, _, queued = queue_upload(client)
    route = f"/v1/encounters/{resource}/audio-uploads/{upload['id']}/complete"
    assert client.post(route, headers=headers()).json() == queued
    job_url = queued["status_url"]
    assert client.get(job_url, headers=headers()).json()["status"] == "queued"
    assets = str(Path(path).parent / "assets")
    result = run_once(path, assets)
    assert result == {"id": queued["job_id"], "status": "succeeded"}
    restarted = TestClient(create_app(path, tokens))
    job = restarted.get(job_url, headers=headers()).json()
    assert job["stage"] == "audio_ingest"
    assert job["result"]["duration_ms"] == 100
    assert job["result"]["sample_rate"] == 16000
    assert job["result"]["sha256"] == hashlib.sha256(wav_bytes()).hexdigest()
    assert job["attempts"] == 1
    assert run_once(path, assets) is None
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_upload_and_job_are_not_visible_to_other_principals(setup):
    client, _, _ = setup
    resource, upload, _, queued = queue_upload(client)
    for token in ("b" * 40, "c" * 40):
        assert client.get(queued["status_url"], headers=headers(token)).status_code == 404
        assert client.put(upload["content_url"], content=wav_bytes(), headers=headers(token)).status_code == 404
        assert client.post(f"/v1/encounters/{resource}/audio-uploads/{upload['id']}/complete",
                           headers=headers(token)).status_code == 404


def test_upload_requires_authorization_and_valid_limits(setup):
    client, _, _ = setup
    resource = create(client)
    route = f"/v1/encounters/{resource}/audio-uploads"
    body = {"bytes": 100, "sha256": "a" * 64}
    assert client.post(route, json=body, headers=headers()).status_code == 403
    for changed in ({"bytes": 250_000_001}, {"bytes": -1}, {"bytes": True},
                    {"sha256": "invalid"}, {"media_type": "audio/mpeg"}, {"filename": "../../escape"}):
        assert client.post(route, json={**body, **changed}, headers=headers()).status_code == 422


def test_checksum_size_and_media_failures_allow_retry(setup):
    client, path, _ = setup
    upload, _ = upload_session(client, create(client), wav_bytes())
    route = upload["content_url"]
    assert client.put(route, content=wav_bytes(), headers={**headers(), "Content-Type": "text/plain"}).status_code == 415
    auth = {**headers(), "Content-Type": "audio/wav"}
    assert client.put(route, content=wav_bytes() + b"x", headers=auth).status_code == 413
    assert client.put(route, content=wav_bytes()[:-1], headers=auth).status_code == 422
    assert client.put(route, content=b"x" * len(wav_bytes()), headers=auth).status_code == 422
    assert client.put(route, content=wav_bytes(), headers=auth).status_code == 200
    assert client.put(route, content=wav_bytes(), headers=auth).status_code == 409
    assert not list((Path(path).parent / "assets").glob("*.part"))


def test_expired_session_and_premature_completion_fail(setup):
    client, path, _ = setup
    resource = create(client)
    upload, _ = upload_session(client, resource, wav_bytes())
    complete = f"/v1/encounters/{resource}/audio-uploads/{upload['id']}/complete"
    assert client.post(complete, headers=headers()).status_code == 409
    with sqlite3.connect(path) as con:
        con.execute("UPDATE uploads SET expires_at='2000-01-01T00:00:00+00:00'")
    assert client.put(upload["content_url"], content=wav_bytes(),
                      headers={**headers(), "Content-Type": "audio/wav"}).status_code == 409


def test_withdrawal_cancels_pending_job(setup):
    client, path, _ = setup
    resource, _, aid, queued = queue_upload(client)
    assert client.post(f"/v1/encounters/{resource}/authorizations/{aid}/withdraw", headers=headers()).status_code == 200
    job = client.get(queued["status_url"], headers=headers()).json()
    assert job["status"] == "cancelled"
    assert job["result"] is None
    assert run_once(path, "unused") is None


def test_revocation_during_worker_prevents_result_publication(setup, monkeypatch):
    client, path, _ = setup
    resource, _, aid, queued = queue_upload(client)
    def inspect_and_revoke(source):
        result = inspect_pcm_wav(source)
        client.post(f"/v1/encounters/{resource}/authorizations/{aid}/withdraw", headers=headers())
        return result
    monkeypatch.setattr("services.api.ingest.inspect_pcm_wav", inspect_and_revoke)
    assert run_once(path, str(Path(path).parent / "assets"))["status"] == "cancelled"
    assert client.get(queued["status_url"], headers=headers()).json()["result"] is None


@pytest.mark.parametrize("content", [b"not-a-wav", wav_bytes()[:-10],
    b"RIFF" + (2**32 - 1).to_bytes(4, "little") + b"WAVE" + b"\0" * 50])
def test_malformed_audio_fails_with_safe_code(setup, content):
    client, path, _ = setup
    _, _, _, queued = queue_upload(client, content)
    assert run_once(path, str(Path(path).parent / "assets"))["status"] == "failed"
    job = client.get(queued["status_url"], headers=headers()).json()
    assert job["error_code"] == "invalid_media"
    assert job["result"] is None


def test_crashed_worker_lease_is_recovered_and_attempts_are_bounded(setup):
    client, path, _ = setup
    _, _, _, queued = queue_upload(client)
    with sqlite3.connect(path) as con:
        con.execute("""UPDATE jobs SET status='running', attempts=3, lease_token='abandoned',
            lease_expires_at='2000-01-01T00:00:00+00:00'""")
    assert run_once(path, "unused") is None
    job = client.get(queued["status_url"], headers=headers()).json()
    assert job["status"] == "failed"
    assert job["error_code"] == "worker_retry_exhausted"


def test_recoverable_worker_crash_retries_original_job(setup):
    client, path, _ = setup
    _, _, _, queued = queue_upload(client)
    with sqlite3.connect(path) as con:
        con.execute("""UPDATE jobs SET status='running', attempts=1, lease_token='abandoned',
            lease_expires_at='2000-01-01T00:00:00+00:00'""")
    assert run_once(path, str(Path(path).parent / "assets"))["status"] == "succeeded"
    assert client.get(queued["status_url"], headers=headers()).json()["attempts"] == 2


def test_concurrent_completion_commits_one_job(setup):
    client, path, tokens = setup
    resource = create(client)
    upload, _ = upload_session(client, resource, wav_bytes())
    assert client.put(upload["content_url"], content=wav_bytes(),
                      headers={**headers(), "Content-Type": "audio/wav"}).status_code == 200
    route = f"/v1/encounters/{resource}/audio-uploads/{upload['id']}/complete"
    def request(_):
        with TestClient(create_app(path, tokens)) as second_client:
            return second_client.post(route, headers=headers())
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(request, range(3)))
    assert all(response.status_code == 202 and response.json() == responses[0].json() for response in responses)
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_expired_authorization_at_dispatch_cancels_job(setup):
    client, path, _ = setup
    _, _, _, queued = queue_upload(client)
    with sqlite3.connect(path) as con:
        body = json.loads(con.execute("SELECT body FROM authorizations").fetchone()[0])
        body["expires_at"] = "2000-01-01T00:00:00+00:00"
        con.execute("UPDATE authorizations SET body=?", (json.dumps(body),))
    assert run_once(path, str(Path(path).parent / "assets"))["status"] == "cancelled"
    assert client.get(queued["status_url"], headers=headers()).json()["attempts"] == 0


def test_tampered_asset_is_not_accepted_by_worker(setup):
    client, path, _ = setup
    _, upload, _, queued = queue_upload(client)
    source = Path(path).parent / "assets" / f"{upload['id']}.wav"
    source.write_bytes(b"x" * len(wav_bytes()))
    assert run_once(path, str(source.parent))["status"] == "failed"
    assert client.get(queued["status_url"], headers=headers()).json()["error_code"] == "asset_integrity_failure"


def test_upload_session_retry_returns_same_session(setup):
    client, path, _ = setup
    resource = create(client)
    route = f"/v1/encounters/{resource}"
    assert client.post(route + "/authorizations", json=authorization(), headers=headers()).status_code == 201
    body = {"bytes": 1234, "sha256": "a" * 64}
    auth = headers()
    first = client.post(route + "/audio-uploads", json=body, headers=auth)
    second = client.post(route + "/audio-uploads", json=body, headers=auth)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert client.post(route + "/audio-uploads", json={**body, "bytes": 1235}, headers=auth).status_code == 409
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM uploads").fetchone()[0] == 1


def test_wav_inspector_rejects_unsupported_format_and_duration(tmp_path):
    from services.api.ingest import InvalidAudio
    base = bytearray(wav_bytes())
    source = tmp_path / "invalid.wav"
    # PCM encoding identifier is at offset 20 in this generated canonical WAV.
    base[20:22] = (3).to_bytes(2, "little")
    source.write_bytes(base)
    with pytest.raises(InvalidAudio, match="unsupported_media"):
        inspect_pcm_wav(source)
    # Sparse file tests the duration bound without allocating the audio in RAM.
    data_bytes = 8000 * 2 * 3601
    header = bytearray(wav_bytes()[:44])
    header[4:8] = (36 + data_bytes).to_bytes(4, "little")
    header[24:28] = (8000).to_bytes(4, "little")
    header[28:32] = (16000).to_bytes(4, "little")
    header[40:44] = data_bytes.to_bytes(4, "little")
    with source.open("wb") as target:
        target.write(header)
        target.truncate(44 + data_bytes)
    with pytest.raises(InvalidAudio, match="duration_limit_exceeded"):
        inspect_pcm_wav(source)
