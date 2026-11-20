"""Synthetic silent PCM through the real local ASR worker; no clinical data."""

import hashlib
import importlib.util
import io
import wave
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from services.api.ingest import run_once as ingest_once
from services.api.main import Identity, create_app
from services.asr.profiles import load_profiles
from services.asr.worker import run_once as transcribe_once
from tests.test_foundation import authorization, headers, payload


def _silent_wav(seconds=2):
    target = io.BytesIO()
    with wave.open(target, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * (16000 * seconds))
    return target.getvalue()


def test_measured_silence_stays_empty_and_cannot_auto_approve(tmp_path):
    if importlib.util.find_spec("faster_whisper") is None:
        pytest.skip("local faster-whisper runtime is unavailable")
    profile_file = Path("data/asr-smoke-profiles.json")
    if not profile_file.is_file():
        pytest.skip("verified local ASR profile is unavailable")
    profile = load_profiles(profile_file)["tiny-en-smoke-v1"]
    if profile.availability()["status"] != "available_not_admitted":
        pytest.skip("verified tiny.en artifacts are unavailable")

    source = _silent_wav()
    digest = hashlib.sha256(source).hexdigest()
    db_path = str(tmp_path / "silence.sqlite3")
    asset_root = str(tmp_path / "assets")
    identity = Identity(tenant_id=uuid4(), clinician_id=uuid4())
    with TestClient(
        create_app(
            db_path,
            {"a" * 40: identity},
            asset_root=asset_root,
            asr_profiles={profile.profile_id: profile},
        )
    ) as client:
        encounter_id = client.post(
            "/v1/encounters", json=payload(), headers=headers()
        ).json()["id"]
        base = f"/v1/encounters/{encounter_id}"
        assert (
            client.post(
                f"{base}/authorizations",
                json=authorization(),
                headers=headers(),
            ).status_code
            == 201
        )
        upload = client.post(
            f"{base}/audio-uploads",
            json={"bytes": len(source), "sha256": digest},
            headers=headers(),
        ).json()
        assert (
            client.put(
                upload["content_url"],
                content=source,
                headers={**headers(), "Content-Type": "audio/wav"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"{base}/audio-uploads/{upload['id']}/complete", headers=headers()
            ).status_code
            == 202
        )

        assert ingest_once(db_path, asset_root)["status"] == "succeeded"
        queued = client.post(
            f"{base}/transcriptions",
            json={
                "audio_asset_id": upload["id"],
                "inference_profile_id": profile.profile_id,
            },
            headers=headers(),
        )
        assert queued.status_code == 202
        assert transcribe_once(db_path, asset_root)["status"] == "succeeded"
        job = client.get(queued.json()["status_url"], headers=headers()).json()
        transcript = client.get(
            job["result"]["transcript_url"], headers=headers()
        ).json()
        assert transcript["status"] == "review_required"
        assert transcript["input_sha256"] == digest
        assert transcript["segments"] == []
        assert "no_transcribed_speech" in transcript["review_flags"]
        assert "digital_silence" in transcript["review_flags"]
        assert transcript["provenance"]["inference_executed"] is False
        assert (
            transcript["provenance"]["inference_mode"]
            == "measured_digital_silence_no_inference"
        )
        assert transcript["provenance"]["timing"].get("inference_seconds") is None
        workspace = client.get(f"{base}/workspace", headers=headers()).json()
        assert workspace["note"] is None
        assert workspace["approval"] is None
