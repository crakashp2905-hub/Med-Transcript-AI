"""Full synthetic audio transaction from upload through exact approved export.

The fixture exercises application and worker wiring only. It is explicitly
classified as transcript replay and is not ASR or clinical quality evidence.
"""

import hashlib

from services.api.ingest import run_once as ingest_once
from services.asr.worker import run_once as transcribe_once
from tests.test_foundation import headers, queue_upload


class ReplayAdapter:
    def __init__(self, profile):
        self.profile = profile

    def transcribe(self, source, metadata, checkpoint):
        checkpoint()
        duration = metadata["duration_ms"] / 1000
        return {
            "segments": [
                {
                    "start_seconds": 0.0,
                    "end_seconds": duration,
                    "text": "Patient reports cough and denies fever.",
                }
            ],
            "duration_seconds": duration,
            "inference_executed": False,
            "provider_mode": "synthetic_fixture",
            "quality_status": "not_an_asr_measurement",
        }


def test_audio_upload_to_exact_approved_export(environment):
    env = environment
    encounter, upload, _, _ = queue_upload(env.client)
    assert ingest_once(env.path, env.assets)["status"] == "succeeded"

    queued = env.client.post(
        f"/v1/encounters/{encounter}/transcriptions",
        json={
            "audio_asset_id": upload["id"],
            "inference_profile_id": env.profile.profile_id,
        },
        headers=headers(),
    )
    assert queued.status_code == 202, queued.text
    assert transcribe_once(env.path, env.assets, ReplayAdapter)["status"] == "succeeded"
    job = env.client.get(queued.json()["status_url"], headers=headers()).json()
    transcript = env.client.get(
        job["result"]["transcript_url"], headers=headers()
    ).json()
    assert transcript["provenance"]["inference_mode"] == "synthetic_transcript_replay"
    assert transcript["segments"][0]["end_ms"] == transcript["duration_ms"]
    assert transcript["segments"][0]["role"] == "unknown"

    base = f"/v1/encounters/{encounter}"
    reviewed = env.client.patch(
        f"{base}/transcripts/{transcript['id']}",
        headers={**headers(), "If-Match": f'"{transcript["sha256"]}"'},
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
            "source_review_reason": "Complete synthetic source reviewed for this test.",
            "correction_reason": "Confirm scripted patient track for transaction test.",
        },
    )
    assert reviewed.status_code == 201, reviewed.text
    tx = reviewed.json()
    facts = env.client.get(f"{base}/facts", headers=headers()).json()["facts"]
    assert facts
    for fact in facts:
        fact.update(
            reviewed=True,
            critical_reviewed=True,
            subject="patient" if fact["subject"] != "family" else "family",
            temporality="current"
            if fact["temporality"] == "unknown"
            else fact["temporality"],
        )

    draft = env.client.post(
        f"{base}/drafts",
        headers=headers(),
        json={"transcript_version_id": tx["id"], "facts": facts},
    )
    assert draft.status_code == 201, draft.text
    note = draft.json()["note"]
    assert draft.json()["verification"]["gate"] == "ready"

    approval = env.client.post(
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
    export = env.client.post(
        f"{base}/exports",
        headers=headers(),
        json={"approval_id": approval.json()["id"], "format": "json"},
    )
    assert export.status_code == 201, export.text
    downloaded = env.client.get(export.json()["download_url"], headers=headers())
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == export.json()["sha256"]
    body = downloaded.json()
    assert body["approval"]["id"] == approval.json()["id"]
    assert body["note"]["id"] == note["id"]
    assert body["note"]["sha256"] == note["sha256"]
    assert body["note"]["transcript_version_id"] == tx["id"]
