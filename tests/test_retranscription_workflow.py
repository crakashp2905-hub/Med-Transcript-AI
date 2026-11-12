"""HTTP -> durable job -> cropped ASR worker -> immutable candidate evidence."""

import sqlite3
import wave
from pathlib import Path
from services.audio_provenance import file_sha256
from services.asr.worker import run_once
from services.inference_slot import local_inference_slot
from tests.test_transcription import enqueue
from tests.test_foundation import headers


def source(env):
    queued = enqueue(env)
    url = f"/v1/encounters/{queued.resource}/manual-transcripts"
    response = env.client.post(
        url,
        headers=headers(),
        json={
            "audio_asset_id": queued.upload["id"],
            "segments": [
                {
                    "start_ms": 0,
                    "end_ms": 100,
                    "text": "unclear dose",
                    "role": "unknown",
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return queued, response.json()


def request(env, queued, tx):
    return env.client.post(
        f"/v1/encounters/{queued.resource}/retranscriptions",
        headers=headers(),
        json={
            "audio_asset_id": queued.upload["id"],
            "transcript_version_id": tx["id"],
            "inference_profile_id": env.profile.profile_id,
            "start_ms": 20,
            "end_ms": 80,
        },
    )


def test_retranscription_worker_crops_real_audio_and_does_not_replace_source(
    environment,
):
    env = environment
    queued, tx = source(env)
    response = request(env, queued, tx)
    assert response.status_code == 202, response.text

    class SpanAdapter:
        def __init__(self, profile):
            pass

        def transcribe(self, path, metadata, checkpoint):
            with wave.open(str(path), "rb") as audio:
                assert audio.getnframes() == 960 and audio.getnchannels() == 1
            checkpoint()
            return {
                "duration_seconds": 0.06,
                "segments": [
                    {"start_seconds": 0, "end_seconds": 0.06, "text": "warfarin 2.5 mg"}
                ],
            }

    # Original queued inference was fenced by the manual source version.
    assert run_once(env.path, env.assets, SpanAdapter)["status"] == "cancelled"
    assert run_once(env.path, env.assets, SpanAdapter)["status"] == "succeeded"
    job = env.client.get(response.json()["status_url"], headers=headers()).json()
    candidate = job["result"]
    assert (
        candidate["candidate_text"] == "warfarin 2.5 mg"
        and candidate["adopted"] is False
    )
    assert candidate["source_transcript_version"] == tx["id"]
    assert candidate["candidate_segments"][0]["start_ms"] == 20
    assert candidate["candidate_segments"][0]["end_ms"] == 80
    assert len(candidate["span_audio_sha256"]) == 64
    source_audio = Path(env.assets) / f"{queued.upload['id']}.wav"
    span_provenance = candidate["span_audio_provenance"]
    assert span_provenance["parent_sha256"] == file_sha256(source_audio)
    assert span_provenance["asset_sha256"] == candidate["span_audio_sha256"]
    assert span_provenance["timeline_mapping"]["kind"] == ("crop_sample_index_offset")
    assert span_provenance["timeline_mapping"]["parent_start_frame"] == 320
    assert span_provenance["timeline_mapping"]["parent_end_frame_exclusive"] == 1280
    assert span_provenance["timeline_mapping"]["channel_index"] == 0
    ws = env.client.get(
        f"/v1/encounters/{queued.resource}/workspace", headers=headers()
    ).json()
    assert ws["transcript"]["id"] == tx["id"] and ws["note"] is None
    with sqlite3.connect(env.path) as con:
        assert (
            con.execute("SELECT COUNT(*) FROM transcript_versions").fetchone()[0] == 1
        )


def test_asr_and_clinical_requests_share_admission_without_claiming_job(environment):
    env = environment
    queued, tx = source(env)
    with local_inference_slot() as ready:
        assert ready
        assert run_once(env.path, env.assets)["status"] == "deferred"
        r = env.client.post(
            f"/v1/encounters/{queued.resource}/fact-proposals",
            headers=headers(),
            json={"transcript_version_id": tx["id"], "mode": "local_model"},
        )
        assert r.status_code == 503
    job = env.client.get(queued.job["status_url"], headers=headers()).json()
    assert job["status"] == "queued" and job["attempts"] == 0


def test_retranscription_rejects_wrong_asset_stale_source_and_out_of_bounds(
    environment,
):
    from uuid import uuid4

    env = environment
    queued, tx = source(env)
    url = f"/v1/encounters/{queued.resource}/retranscriptions"
    body = {
        "audio_asset_id": queued.upload["id"],
        "transcript_version_id": tx["id"],
        "inference_profile_id": env.profile.profile_id,
        "start_ms": 20,
        "end_ms": 80,
    }
    for patch, status in [
        ({"audio_asset_id": str(uuid4())}, 422),
        ({"transcript_version_id": str(uuid4())}, 412),
        ({"end_ms": 200}, 422),
    ]:
        assert (
            env.client.post(url, headers=headers(), json={**body, **patch}).status_code
            == status
        )
    assert env.client.post(url, headers=headers("b" * 40), json=body).status_code == 404
