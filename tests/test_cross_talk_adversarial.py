import hashlib
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from services.api.ingest import run_once as ingest_once
from services.api.main import Identity, create_app
from services.asr.profiles import load_profiles
from services.asr.cross_talk_adversarial import RESERVED_GROUPS, SCENARIO_ID
from services.asr.worker import run_once as transcribe_once
from tests.test_foundation import authorization, headers, payload


ROOT = Path(__file__).resolve().parents[1]


def test_cross_talk_challenge_is_source_bound_and_nonreserved():
    scenario_path = ROOT / "evaluation/scenarios/offline-encounters-v1/manifest.json"
    manifest = json.loads(scenario_path.read_text(encoding="utf-8"))
    rows = [row for row in manifest["scenarios"] if row["scenario_id"] == SCENARIO_ID]
    assert len(rows) == 1
    scenario = rows[0]
    assert scenario["scenario_type"] == "overlapping"
    assert scenario["source_group_id"] not in RESERVED_GROUPS
    assert scenario["channels"] == 1
    assert scenario["audio_transform"]["overlap_ms"] > 0
    assert len(scenario["transcript_turns"]) == 2
    first, second = scenario["transcript_turns"]
    assert max(first["start_ms"], second["start_ms"]) < min(
        first["end_ms"], second["end_ms"]
    )
    audio = (
        ROOT / "evaluation/scenarios/offline-encounters-v1" / scenario["audio_asset"]
    )
    assert hashlib.sha256(audio.read_bytes()).hexdigest() == scenario["audio_sha256"]
    source_manifest = ROOT / "evaluation/datasets/primock57-expanded-v1/manifest.json"
    assert (
        hashlib.sha256(source_manifest.read_bytes()).hexdigest()
        == scenario["source_dataset_manifest_sha256"]
    )


def test_real_asr_worker_keeps_cross_talk_transcript_in_review(tmp_path):
    if importlib.util.find_spec("faster_whisper") is None:
        pytest.skip("local faster-whisper runtime is unavailable")
    profile_file = ROOT / "data/asr-smoke-profiles.json"
    if not profile_file.is_file():
        pytest.skip("verified local ASR profile is unavailable")
    profile = load_profiles(profile_file)["tiny-en-smoke-v1"]
    if profile.availability()["status"] != "available_not_admitted":
        pytest.skip("verified tiny.en artifacts are unavailable")

    manifest = json.loads(
        (ROOT / "evaluation/scenarios/offline-encounters-v1/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    scenario = next(
        row for row in manifest["scenarios"] if row["scenario_id"] == SCENARIO_ID
    )
    source = (
        ROOT / "evaluation/scenarios/offline-encounters-v1" / scenario["audio_asset"]
    )
    audio_bytes = source.read_bytes()
    assert hashlib.sha256(audio_bytes).hexdigest() == scenario["audio_sha256"]
    db_path = str(tmp_path / "cross-talk.sqlite3")
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
            json={"bytes": len(audio_bytes), "sha256": scenario["audio_sha256"]},
            headers=headers(),
        ).json()
        assert (
            client.put(
                upload["content_url"],
                content=audio_bytes,
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
        assert transcript["segments"]
        workspace = client.get(f"{base}/workspace", headers=headers()).json()
        assert workspace["note"] is None
        assert workspace["approval"] is None
