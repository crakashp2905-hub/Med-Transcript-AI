import hashlib
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from services.api.ingest import run_once as ingest_once
from services.api.main import Identity, create_app
from services.asr.spoken_prompt_adversarial import PROMPT_TEXT
from services.asr.profiles import load_profiles
from services.asr.worker import run_once as transcribe_once
from services.prompt_injection import inspect
from tests.test_foundation import authorization, headers, payload


ROOT = Path(__file__).resolve().parents[1]


def test_spoken_prompt_challenge_keeps_transcript_inert_as_source_data():
    result = inspect(PROMPT_TEXT)
    assert result["untrusted"] is True
    assert result["application_control"] is False
    assert result["file_access"] is False
    assert result["approval_control"] is False
    assert set(result["markers"]) == {
        "approve the note",
        "ignore previous instructions",
        "read file",
    }


def test_worker_rejects_bad_timestamps_and_creates_no_note_or_approval(tmp_path):
    if importlib.util.find_spec("faster_whisper") is None:
        pytest.skip("local faster-whisper runtime is unavailable")
    audio_path = (
        ROOT / "evaluation/runs/asr-adversarial-spoken-prompt-v3/spoken_prompt.wav"
    )
    report_path = ROOT / "evaluation/runs/asr-adversarial-spoken-prompt-v4/report.json"
    profile_file = ROOT / "data/asr-smoke-profiles.json"
    if (
        not audio_path.is_file()
        or not report_path.is_file()
        or not profile_file.is_file()
    ):
        pytest.skip("locally synthesized speech fixture or report is unavailable")
    audio = audio_path.read_bytes()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert hashlib.sha256(audio).hexdigest() == report["audio_sha256"]
    assert report["transcript_validation_error"] == "invalid_asr_output"
    profile = load_profiles(profile_file)["tiny-en-smoke-v1"]
    if profile.availability()["status"] != "available_not_admitted":
        pytest.skip("verified tiny.en artifacts are unavailable")

    db_path = str(tmp_path / "spoken-prompt.sqlite3")
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
            json={"bytes": len(audio), "sha256": report["audio_sha256"]},
            headers=headers(),
        ).json()
        assert (
            client.put(
                upload["content_url"],
                content=audio,
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
        result = transcribe_once(db_path, asset_root)
        assert result["status"] == "failed"
        job = client.get(queued.json()["status_url"], headers=headers()).json()
        assert job["error_code"] == "invalid_asr_output"
        assert job.get("result") is None
        workspace = client.get(f"{base}/workspace", headers=headers()).json()
        assert workspace["note"] is None
        assert workspace["approval"] is None
