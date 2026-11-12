"""Offline real-model workflow smoke; scripted review is not clinical acceptance."""

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from services.api.ingest import run_once as ingest_once
from services.api.main import Identity, create_app
from services.asr.profiles import load_profiles
from services.asr.worker import run_once as transcribe_once
from tests.test_foundation import authorization, headers, payload


def test_real_local_asr_reaches_reviewed_approved_export(tmp_path):
    profile_file = Path("data/asr-smoke-profiles.json")
    audio = Path(
        "data/datasets/primock57-smoke/"
        "day1_consultation01_patient.utterance01.wav"
    )
    if not profile_file.is_file() or not audio.is_file():
        pytest.skip("local model profile or licensed mock audio is unavailable")
    profile = load_profiles(profile_file)["tiny-en-smoke-v1"]
    if profile.availability()["status"] != "available_not_admitted":
        pytest.skip("verified tiny.en model weights are unavailable")

    source = audio.read_bytes()
    db_path = str(tmp_path / "workflow.sqlite3")
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
        encounter = client.post(
            "/v1/encounters", json=payload(), headers=headers()
        ).json()["id"]
        base = f"/v1/encounters/{encounter}"
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
            json={
                "bytes": len(source),
                "sha256": hashlib.sha256(source).hexdigest(),
            },
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
                f"{base}/audio-uploads/{upload['id']}/complete",
                headers=headers(),
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
        assert queued.status_code == 202, queued.text
        worker_result = transcribe_once(db_path, asset_root)
        assert worker_result["status"] == "succeeded", worker_result
        job = client.get(queued.json()["status_url"], headers=headers()).json()
        assert job["status"] == "succeeded"
        transcript = client.get(
            job["result"]["transcript_url"], headers=headers()
        ).json()
        assert transcript["status"] == "review_required"
        assert transcript["input_sha256"] == hashlib.sha256(source).hexdigest()
        assert transcript["provenance"]["profile_sha256"] == profile.sha256
        assert transcript["segments"]
        assert all(
            segment["timestamp_kind"] == "native_segment"
            and segment["end_ms"] > segment["start_ms"]
            for segment in transcript["segments"]
        )
        assert all(
            segment["decoder_evidence"]["kind"]
            == "faster_whisper_best_sequence_v1"
            and segment["decoder_evidence"]["token_ids"]
            and segment["decoder_evidence"]["average_logprob"] <= 0
            and segment["decoder_evidence"]["n_best_supported"] is False
            and segment["decoder_evidence"]["calibrated"] is False
            for segment in transcript["segments"]
        )

        # This scripted attestation exercises the workflow mechanics only.
        reviewed = client.patch(
            f"{base}/transcripts/{transcript['id']}",
            headers={
                **headers(),
                "If-Match": f'"{transcript["sha256"]}"',
            },
            json={
                "segments": [
                    {
                        "segment_id": segment["segment_id"],
                        "text": segment["text"],
                        "role": "patient",
                    }
                    for segment in transcript["segments"]
                ],
                "english_confirmed": True,
                "source_completeness_reviewed": True,
                "source_review_reason": (
                    "Scripted public mock review covers this utterance and audio."
                ),
                "correction_reason": (
                    "Source coverage and patient track are confirmed for this test."
                ),
            },
        )
        assert reviewed.status_code == 201, reviewed.text
        current_transcript = reviewed.json()
        facts = client.get(f"{base}/facts", headers=headers()).json()["facts"]
        assert facts
        for fact in facts:
            fact.update(
                reviewed=True,
                subject="patient",
                temporality="current",
                critical_reviewed=True,
            )
        draft = client.post(
            f"{base}/drafts",
            headers=headers(),
            json={
                "transcript_version_id": current_transcript["id"],
                "facts": facts,
            },
        )
        assert draft.status_code == 201, draft.text
        note = draft.json()["note"]
        assert draft.json()["verification"]["gate"] == "ready"
        approval = client.post(
            f"{base}/approvals",
            headers=headers(),
            json={
                "note_version_id": note["id"],
                "expected_note_sha256": note["sha256"],
                "verification_report_id": note["verification_report_id"],
                "patient_identifiers_reconfirmed": True,
            },
        )
        assert approval.status_code == 201, approval.text
        export = client.post(
            f"{base}/exports",
            headers=headers(),
            json={"approval_id": approval.json()["id"], "format": "json"},
        )
        assert export.status_code == 201, export.text
        downloaded = client.get(export.json()["download_url"], headers=headers())
        assert downloaded.status_code == 200
        assert hashlib.sha256(downloaded.content).hexdigest() == export.json()["sha256"]
