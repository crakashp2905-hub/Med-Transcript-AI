import hashlib
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from services.api.ingest import run_once as ingest_once
from services.api.main import Identity, create_app
from services.api.storage import Store
from services.asr.adapter import ASRFailure, FasterWhisperAdapter
from services.asr.profiles import ASRProfile, REQUIRED_FILES, content_sha256
from services.asr.transcripts import build_transcript
from services.asr.worker import run_once as transcribe_once
from tests.test_foundation import headers, queue_upload, wav_bytes


@pytest.fixture
def environment(tmp_path):
    root = tmp_path / "model"
    root.mkdir()
    for name in REQUIRED_FILES:
        (root / name).write_bytes(b"synthetic-unit-test-artifact")
    profile = ASRProfile(profile_id="synthetic-test-v1", model_dir=str(root),
        source="synthetic-fixture", revision="a" * 40, license_id="test-only",
        artifacts={name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in REQUIRED_FILES})
    path = str(tmp_path / "test.sqlite3")
    tenant = uuid4()
    tokens = {"a" * 40: Identity(tenant_id=tenant, clinician_id=uuid4()),
              "b" * 40: Identity(tenant_id=uuid4(), clinician_id=uuid4()),
              "c" * 40: Identity(tenant_id=tenant, clinician_id=uuid4())}
    client = TestClient(create_app(path, tokens, asr_profiles={profile.profile_id: profile}))
    return SimpleNamespace(client=client, path=path, assets=str(tmp_path / "assets"),
                           profile=profile, tokens=tokens)


class SyntheticAdapter:
    def __init__(self, profile):
        self.profile = profile

    def transcribe(self, source, metadata, checkpoint):
        checkpoint()
        return {"segments": [{"start_seconds": 0.0, "end_seconds": 0.08,
                              "text": " Synthetic unit test."}],
                "duration_seconds": metadata["frames"] / 16000,
                "digital_silence": False, "inference_executed": True}


def enqueue(env):
    resource, upload, aid, _ = queue_upload(env.client)
    assert ingest_once(env.path, env.assets)["status"] == "succeeded"
    body = {"audio_asset_id": upload["id"], "inference_profile_id": env.profile.profile_id}
    route = f"/v1/encounters/{resource}/transcriptions"
    queued = env.client.post(route, json=body, headers=headers())
    assert queued.status_code == 202
    return SimpleNamespace(resource=resource, upload=upload, authorization_id=aid,
                           body=body, route=route, job=queued.json())


def test_transcription_end_to_end_preserves_provenance_and_immutable_hash(environment):
    env = environment
    queued = enqueue(env)
    completion = env.client.post(f"/v1/encounters/{queued.resource}/audio-uploads/{queued.upload['id']}/complete",
                                 headers=headers()).json()
    assert completion["job_id"] != queued.job["job_id"]
    assert ingest_once(env.path, env.assets) is None  # Ingest never claims an ASR job.
    assert transcribe_once(env.path, env.assets, SyntheticAdapter)["status"] == "succeeded"
    job = env.client.get(queued.job["status_url"], headers=headers()).json()
    assert job["stage"] == "transcription"
    assert job["profile_sha256"] == env.profile.sha256
    url = job["result"]["transcript_url"]
    response = env.client.get(url, headers=headers())
    body = response.json()
    assert body["segments"][0]["text"] == " Synthetic unit test."
    assert body["segments"][0]["role"] == "unknown"
    assert body["segments"][0]["language_status"] == "uncertain"
    assert body["untranscribed_intervals"] == [{"start_ms": 80, "end_ms": 100,
                                               "reason": "not_transcribed_unknown_cause"}]
    assert body["status"] == "review_required"
    assert body["provenance"]["clinical_coverage"] == "unverified"
    digest = body.pop("sha256")
    assert content_sha256(body) == digest
    assert response.headers["etag"] == f'"{digest}"'
    assert "model_dir" not in response.text
    restarted = TestClient(create_app(env.path, env.tokens))
    assert restarted.get(url, headers=headers()).json()["sha256"] == digest
    with sqlite3.connect(env.path) as con:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            con.execute("UPDATE transcript_versions SET body='{}'")
        assert con.execute("SELECT COUNT(*) FROM transcript_versions").fetchone()[0] == 1


def test_transcription_queue_deduplicates_different_keys(environment):
    env = environment
    queued = enqueue(env)
    def request(_):
        with TestClient(create_app(env.path, env.tokens, asr_profiles={env.profile.profile_id: env.profile})) as client:
            return client.post(queued.route, json=queued.body, headers=headers())
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(request, range(3)))
    assert all(response.status_code == 202 and response.json() == queued.job for response in responses)
    with sqlite3.connect(env.path) as con:
        assert con.execute("SELECT COUNT(*) FROM jobs WHERE stage='transcription'").fetchone()[0] == 1


def test_cross_tenant_and_unassigned_clinician_cannot_access_transcript(environment):
    env = environment
    queued = enqueue(env)
    transcribe_once(env.path, env.assets, SyntheticAdapter)
    url = env.client.get(queued.job["status_url"], headers=headers()).json()["result"]["transcript_url"]
    for token in ("b" * 40, "c" * 40):
        assert env.client.get(url, headers=headers(token)).status_code == 404
        assert env.client.post(queued.route, json=queued.body, headers=headers(token)).status_code == 404
    assert env.client.get(url.replace(queued.resource, str(uuid4())), headers=headers()).status_code == 404


def test_transcription_requires_completed_ingest_and_configured_profile(environment):
    env = environment
    resource, upload, _, _ = queue_upload(env.client)
    route = f"/v1/encounters/{resource}/transcriptions"
    body = {"audio_asset_id": upload["id"], "inference_profile_id": env.profile.profile_id}
    assert env.client.post(route, json=body, headers=headers()).status_code == 409
    assert env.client.post(route, json={**body, "inference_profile_id": "unknown"}, headers=headers()).status_code == 503
    assert env.client.post(route, json={**body, "model_dir": "client-path"}, headers=headers()).status_code == 422


def test_withdrawal_during_inference_discards_late_transcript(environment):
    env = environment
    queued = enqueue(env)
    class RevokeAdapter(SyntheticAdapter):
        def transcribe(self, source, metadata, checkpoint):
            result = super().transcribe(source, metadata, checkpoint)
            env.client.post(f"/v1/encounters/{queued.resource}/authorizations/{queued.authorization_id}/withdraw",
                            headers=headers())
            return result
    assert transcribe_once(env.path, env.assets, RevokeAdapter)["status"] == "cancelled"
    job = env.client.get(queued.job["status_url"], headers=headers()).json()
    assert job["result"] is None
    with sqlite3.connect(env.path) as con:
        assert con.execute("SELECT COUNT(*) FROM transcript_versions").fetchone()[0] == 0


def test_partial_adapter_failure_never_publishes_content(environment):
    env = environment
    queued = enqueue(env)
    class BrokenAdapter(SyntheticAdapter):
        def transcribe(self, *_):
            raise RuntimeError("private transcript fragment and provider exception")
    assert transcribe_once(env.path, env.assets, BrokenAdapter)["status"] == "failed"
    response = env.client.get(queued.job["status_url"], headers=headers())
    assert response.json()["error_code"] == "asr_failed"
    assert "private transcript" not in response.text
    assert response.json()["result"] is None


@pytest.mark.parametrize("replacement", [None, {"segments": [], "duration_seconds": 1.0},
    {"segments": [{"start_seconds": 0, "end_seconds": float("nan"), "text": "bad"}], "duration_seconds": 0.1},
    {"segments": [{"start_seconds": 0, "end_seconds": 0.08, "text": "\ud800"}], "duration_seconds": 0.1},
    {"segments": [{"start_seconds": 0, "end_seconds": 50, "text": "bad"}], "duration_seconds": 0.1}])
def test_invalid_output_cannot_create_transcript(environment, replacement):
    env = environment
    queued = enqueue(env)
    class InvalidAdapter(SyntheticAdapter):
        def transcribe(self, *_):
            return replacement
    assert transcribe_once(env.path, env.assets, InvalidAdapter)["status"] == "failed"
    assert env.client.get(queued.job["status_url"], headers=headers()).json()["error_code"] == "invalid_asr_output"


def test_single_heavy_worker_claim_is_enforced(environment):
    env = environment
    queued = enqueue(env)
    class NestedAdapter(SyntheticAdapter):
        def transcribe(self, source, metadata, checkpoint):
            assert transcribe_once(env.path, env.assets, SyntheticAdapter) is None
            return super().transcribe(source, metadata, checkpoint)
    assert transcribe_once(env.path, env.assets, NestedAdapter)["status"] == "succeeded"
    assert env.client.get(queued.job["status_url"], headers=headers()).json()["attempts"] == 1


def test_asr_abandoned_worker_is_recovered(environment):
    env = environment
    queued = enqueue(env)
    with sqlite3.connect(env.path) as con:
        con.execute("""UPDATE jobs SET status='running',attempts=1,lease_token='old',
            lease_expires_at='2000-01-01T00:00:00+00:00' WHERE stage='transcription'""")
    assert transcribe_once(env.path, env.assets, SyntheticAdapter)["status"] == "succeeded"
    assert env.client.get(queued.job["status_url"], headers=headers()).json()["attempts"] == 2


def test_superseded_lease_cannot_publish_transcript(environment):
    env = environment
    queued = enqueue(env)
    class LostLeaseAdapter(SyntheticAdapter):
        def transcribe(self, source, metadata, checkpoint):
            result = super().transcribe(source, metadata, checkpoint)
            with Store(env.path).transaction() as con:
                con.execute("UPDATE jobs SET lease_token='new-owner' WHERE id=?", (queued.job["job_id"],))
            return result
    assert transcribe_once(env.path, env.assets, LostLeaseAdapter)["status"] == "running"
    with sqlite3.connect(env.path) as con:
        assert con.execute("SELECT COUNT(*) FROM transcript_versions").fetchone()[0] == 0
        assert con.execute("SELECT lease_token FROM jobs WHERE stage='transcription'").fetchone()[0] == "new-owner"


def test_human_source_change_fences_late_asr_result(environment):
    env = environment
    queued = enqueue(env)
    class HumanEditAdapter(SyntheticAdapter):
        def transcribe(self, source, metadata, checkpoint):
            result = super().transcribe(source, metadata, checkpoint)
            with Store(env.path).transaction() as con:
                con.execute("UPDATE encounters SET current_transcript=? WHERE id=?", (str(uuid4()), queued.resource))
            return result
    assert transcribe_once(env.path, env.assets, HumanEditAdapter)["status"] == "cancelled"
    job = env.client.get(queued.job["status_url"], headers=headers()).json()
    assert job["error_code"] == "transcript_changed" and job["result"] is None


def test_version_two_migration_preserves_ingest_jobs(tmp_path):
    from services.api.storage import MIGRATIONS
    path = str(tmp_path / "version-two.sqlite3")
    with sqlite3.connect(path) as con:
        for migration in MIGRATIONS[:2]:
            con.executescript(migration)
        con.execute("INSERT INTO encounters VALUES ('enc','tenant','clinician','{}','2026-01-01')")
        con.execute("INSERT INTO uploads VALUES ('upload','enc',44,?,'complete','2026-01-01','2026-01-02')", ("a" * 64,))
        con.execute("""INSERT INTO jobs (id,upload,encounter,status,created_at,updated_at,result)
            VALUES ('original-job','upload','enc','succeeded','2026-01-01','2026-01-01','{}')""")
        con.execute("PRAGMA user_version=2")
    with Store(path).transaction() as con:
        row = con.execute("SELECT * FROM jobs WHERE id='original-job'").fetchone()
        assert row["status"] == "succeeded" and row["stage"] == "audio_ingest"
        assert not con.execute("PRAGMA foreign_key_check").fetchall()


def test_profile_requires_local_paths_and_detects_tampered_artifacts(environment):
    profile = environment.profile
    profile.verify_artifacts()
    (Path(profile.model_dir) / "tokenizer.json").unlink()
    with pytest.raises(ValueError, match="model_integrity_failure"):
        profile.verify_artifacts()
    for changed in ({"model_dir": "remote/model-id"}, {"revision": "main"},
                    {"artifacts": {**profile.artifacts, "../outside": "a" * 64}}):
        with pytest.raises(ValueError):
            ASRProfile.model_validate({**profile.model_dump(), **changed})


def test_model_adapter_uses_only_local_files_and_consumes_lazy_segments(environment, monkeypatch):
    pytest.importorskip("numpy")
    env = environment
    source = Path(env.assets)
    source.mkdir(exist_ok=True)
    audio = bytearray(wav_bytes())
    audio[-2:] = b"\1\0"  # Nonzero PCM avoids the exact-digital-silence shortcut.
    wav = source / "synthetic.wav"
    wav.write_bytes(audio)
    calls, consumed = {}, []
    class Model:
        def __init__(self, model_dir, **kwargs):
            calls.update({"model_dir": model_dir, **kwargs})
        def transcribe(self, samples, **kwargs):
            calls["transcribe"] = kwargs
            assert len(samples) == 1600
            def lazy():
                consumed.append(True)
                yield SimpleNamespace(start=0.0, end=0.08, text=" synthetic")
            return lazy(), SimpleNamespace(duration=0.1)
    monkeypatch.setattr("services.asr.adapter.importlib.metadata.version", lambda _: "1.2.1")
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Model))
    raw = FasterWhisperAdapter(env.profile).transcribe(wav, {"frames": 1600, "channels": 1,
                "sample_rate": 16000}, lambda: None)
    assert consumed == [True]
    assert raw["segments"][0]["text"] == " synthetic"
    assert calls["local_files_only"] is True
    assert calls["model_dir"] == env.profile.model_dir
    assert calls["transcribe"]["language"] == "en"
    assert calls["transcribe"]["task"] == "transcribe"
    assert calls["transcribe"]["vad_filter"] is False
    assert calls["transcribe"]["word_timestamps"] is False


def test_digital_silence_does_not_invoke_model(environment, monkeypatch):
    pytest.importorskip("numpy")
    env = environment
    source = Path(env.assets)
    source.mkdir(exist_ok=True)
    wav = source / "silence.wav"
    wav.write_bytes(wav_bytes())
    def forbidden_model(*_, **__):
        raise AssertionError("Silence must not cause model-generated clinical text")
    monkeypatch.setattr("services.asr.adapter.importlib.metadata.version", lambda _: "1.2.1")
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=forbidden_model))
    raw = FasterWhisperAdapter(env.profile).transcribe(wav, {"frames": 1600, "channels": 1,
                "sample_rate": 16000}, lambda: None)
    assert raw["segments"] == [] and raw["inference_executed"] is False
