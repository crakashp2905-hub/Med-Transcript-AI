"""Multichannel transport, isolation, overlap and all-or-nothing worker publishing."""

import io
import wave

import pytest

from services.api.ingest import inspect_pcm_wav, run_once as ingest_once, InvalidAudio
from services.asr.adapter import ASRFailure
from services.asr.worker import run_once
from tests.test_foundation import headers, queue_upload
from tests.test_transcription import SyntheticAdapter


def recording(count, rate=16000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setparams((count, 2, rate, 0, "NONE", "not compressed"))
        audio.writeframes(
            b"".join((index + 1).to_bytes(2, "little") for index in range(count))
            * (rate // 10)
        )
    return buffer.getvalue()


def queued(env, count):
    eid, upload, _, ingest = queue_upload(env.client, recording(count))
    assert ingest_once(env.path, env.assets)["status"] == "succeeded"
    job = env.client.post(
        f"/v1/encounters/{eid}/transcriptions",
        headers=headers(),
        json={
            "audio_asset_id": upload["id"],
            "inference_profile_id": env.profile.profile_id,
        },
    )
    assert job.status_code == 202, job.text
    return eid, upload


@pytest.mark.parametrize("count", [2, 3, 8])
def test_isolated_channels_overlap_and_scoped_playback(environment, count):
    env = environment
    eid, upload = queued(env, count)
    seen = []

    class Adapter(SyntheticAdapter):
        def transcribe(self, source, metadata, checkpoint):
            with wave.open(str(source), "rb") as audio:
                assert audio.getnchannels() == 1
                value = int.from_bytes(audio.readframes(1), "little")
                assert audio.readframes(1600) == value.to_bytes(2, "little") * 1599
            seen.append(value)
            return super().transcribe(source, metadata, checkpoint)

    assert run_once(env.path, env.assets, Adapter)["status"] == "succeeded"
    assert seen == list(range(1, count + 1))
    tx = env.client.get(f"/v1/encounters/{eid}/workspace", headers=headers()).json()[
        "transcript"
    ]
    assert len(tx["channels"]) == count
    assert [s["channel_index"] for s in tx["segments"]] == list(range(count))
    source_provenance = tx["provenance"]["audio_provenance"]
    assert source_provenance["asset_sha256"] == tx["input_sha256"]
    for index, channel in enumerate(tx["channels"]):
        lineage = channel["provenance"]["derived_audio_provenance"]
        timeline = lineage["timeline_mapping"]
        assert lineage["parent_sha256"] == source_provenance["asset_sha256"]
        assert (
            lineage["asset_sha256"]
            == channel["provenance"]["isolated_channel_pcm_sha256"]
        )
        assert timeline["channel_index"] == index
        assert timeline["channel_count"] == count
        assert timeline["parent_frames"] == timeline["output_frames"] == 1600
    assert all(
        s["start_ms"] == 0
        and s["end_ms"] == 80
        and s["role"] == "unknown"
        and s["role_status"] == "unconfirmed"
        for s in tx["segments"]
    )
    assert {g["channel_index"] for g in tx["untranscribed_intervals"]} == set(
        range(count)
    )
    route = f"/v1/encounters/{eid}/audio/{upload['id']}?channel={count - 1}"
    response = env.client.get(route, headers=headers())
    assert response.status_code == 200
    with wave.open(io.BytesIO(response.content), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.readframes(1600) == count.to_bytes(2, "little") * 1600
    assert env.client.get(route, headers=headers("b" * 40)).status_code == 404
    assert (
        env.client.get(
            f"/v1/encounters/{eid}/audio/{upload['id']}?channel={count}",
            headers=headers(),
        ).status_code
        == 422
    )
    # A source correction retains channel identity and makes a new immutable version.
    body = {
        "segments": [
            {
                "segment_id": s["segment_id"],
                "text": s["text"],
                "role": "interpreter" if s["channel_index"] == count - 1 else "unknown",
            }
            for s in tx["segments"]
        ],
        "english_confirmed": True,
        "source_completeness_reviewed": False,
        "source_review_reason": "Review pending",
        "correction_reason": "Confirm interpreter channel",
    }
    edited = env.client.patch(
        f"/v1/encounters/{eid}/transcripts/{tx['id']}",
        headers={**headers(), "If-Match": f'"{tx["sha256"]}"'},
        json=body,
    )
    assert edited.status_code == 201, edited.text
    assert edited.json()["segments"][-1]["channel_index"] == count - 1
    assert edited.json()["segments"][-1]["role"] == "interpreter"


def test_failed_channel_never_publishes_partial_transcript(environment):
    env = environment
    eid, _ = queued(env, 3)

    class Broken(SyntheticAdapter):
        def transcribe(self, source, metadata, checkpoint):
            with wave.open(str(source), "rb") as audio:
                if audio.readframes(1) == b"\x02\x00":
                    raise ASRFailure("asr_failed")
            return super().transcribe(source, metadata, checkpoint)

    assert run_once(env.path, env.assets, Broken)["status"] == "failed"
    assert (
        env.client.get(f"/v1/encounters/{eid}/workspace", headers=headers()).json()[
            "transcript"
        ]
        is None
    )


def test_ninth_channel_rejected(tmp_path):
    source = tmp_path / "nine.wav"
    source.write_bytes(recording(9))
    with pytest.raises(InvalidAudio):
        inspect_pcm_wav(source)


@pytest.mark.parametrize("swapped", [False, True])
def test_channel_isolation_preserves_cross_talk_gain_and_physical_order(
    tmp_path, swapped
):
    """Isolation must preserve the recording, not infer speakers or undo bleed."""
    from array import array

    from services.asr.channels import write_channel

    rate = 16000
    left_voice = [900, -900, 450, -450] * 4
    right_voice = [120, 240, -120, -240] * 4  # deliberately asymmetric mic gain
    left, right = left_voice.copy(), right_voice.copy()
    # A synthetic overlap interval contains cross-talk in both physical channels.
    left[4:8] = [left_voice[i] + right_voice[i] for i in range(4, 8)]
    right[4:8] = [right_voice[i] + left_voice[i] // 10 for i in range(4, 8)]
    channels = [right, left] if swapped else [left, right]
    interleaved = array("h", (sample for frame in zip(*channels) for sample in frame))
    source = tmp_path / f"cross-talk-{swapped}.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setparams((2, 2, rate, 0, "NONE", "not compressed"))
        audio.writeframes(interleaved.tobytes())

    isolated = []
    for channel in range(2):
        target = tmp_path / f"isolated-{swapped}-{channel}.wav"
        provenance = write_channel(source, target, channel)
        with wave.open(str(target), "rb") as audio:
            assert audio.getnchannels() == 1
            assert audio.getframerate() == rate
            isolated.append(audio.readframes(audio.getnframes()))
        assert provenance["timeline_mapping"]["channel_index"] == channel

    expected = [array("h", values).tobytes() for values in channels]
    assert isolated == expected
    # The two channels remain distinct despite overlap and unequal gain.
    assert isolated[0] != isolated[1]


def test_decoder_preserves_three_distinct_channels(tmp_path):
    pytest.importorskip("av")
    from services.media_decoder import normalize

    source = tmp_path / "three.wav"
    target = tmp_path / "normalized.wav"
    source.write_bytes(recording(3, 48000))
    assert normalize(source, target, "audio/wav")["error_code"] is None
    assert inspect_pcm_wav(target)["channels"] == 3
    with wave.open(str(target), "rb") as audio:
        import numpy as np

        values = np.frombuffer(audio.readframes(1600), dtype="<i2").reshape(-1, 3)
        assert (values[100:] == [1, 2, 3]).all()


def test_multichannel_provenance_does_not_relabel_first_channel_as_whole_job(
    environment,
):
    from services.asr.channels import build_channels

    profile = environment.profile
    silent = {
        "segments": [],
        "duration_seconds": 0.1,
        "digital_silence": True,
        "inference_executed": False,
    }
    speech = {
        "segments": [{"start_seconds": 0, "end_seconds": 0.08, "text": "synthetic"}],
        "duration_seconds": 0.1,
        "inference_executed": True,
        "isolated_channel_pcm_sha256": "b" * 64,
        "timing": {
            "model_cache_hit": True,
            "model_load_seconds": 2,
            "inference_seconds": 3,
        },
    }
    from uuid import uuid4

    value = build_channels(
        {"channel_outputs": [silent, speech]},
        {"channels": 2, "duration_ms": 100, "sha256": "a" * 64},
        str(uuid4()),
        str(uuid4()),
        profile,
        str(uuid4()),
        1,
    )
    assert value["provenance"]["inference_executed"] is True
    assert value["provenance"]["inference_mode"] == "real_model_inference"
    assert "digital_silence" not in value["review_flags"]
    assert value["channels"][0]["provenance"]["inference_executed"] is False
    assert value["channels"][0]["provenance"]["timing"] == {}
    assert value["provenance"]["timing"]["summed_channel_inference_seconds"] == 3
    assert value["provenance"]["timing"]["cached_channels"] == 1
    assert value["provenance"]["timing"]["summed_model_load_seconds"] == 2
    assert "isolated_channel_pcm_sha256" not in value["provenance"]
    trace = value["timeline_trace"]
    assert trace["duration_ms"] == 100
    assert trace["covered_ms"] == 80
    assert trace["uncovered_ms"] == 20
    assert trace["coverage_percent"] == 80.0
    assert [channel["covered_ms"] for channel in trace["channels"]] == [0, 80]
    assert trace["clinical_completeness"] == "unverified"
    assert value["suppressed_channel_segments"] == []
    assert [row["segment_id"] for row in value["channel_postprocessing_log"]] == [
        row["segment_id"] for row in value["segments"]
    ]


def test_channel_pipeline_keeps_ambiguous_duplicate_evidence_reviewable(environment):
    from uuid import uuid4
    from services.asr.channels import build_channels

    profile = environment.profile
    speech = {
        "segments": [
            {"start_seconds": 0.1, "end_seconds": 0.8, "text": "Take one tablet."}
        ],
        "duration_seconds": 1.0,
        "inference_executed": True,
    }
    value = build_channels(
        {"channel_outputs": [speech, speech]},
        {"channels": 2, "duration_ms": 1000, "sha256": "c" * 64},
        str(uuid4()),
        str(uuid4()),
        profile,
        str(uuid4()),
        1,
    )

    assert len(value["segments"]) == 2
    assert value["suppressed_channel_segments"] == []
    assert len(value["duplicate_channel_speech_candidates"]) == 1
    assert "duplicate_channel_speech_requires_review" in value["review_flags"]
    assert (
        value["duplicate_channel_speech_candidates"][0]["requires_human_review"] is True
    )
    assert len(value["channel_postprocessing_log"]) == 2
    assert {row["channel_index"] for row in value["channel_postprocessing_log"]} == {
        0,
        1,
    }
