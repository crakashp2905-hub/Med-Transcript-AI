"""Bounded channel isolation; channel identity never implies a clinical role."""

import tempfile
from copy import deepcopy
import wave
from pathlib import Path

from services.api.ingest import MAX_CHANNELS, inspect_pcm_wav, file_sha256
from services.asr.adapter import ASRFailure
from services.asr.transcripts import build_transcript
from services.audio_provenance import (
    channel_timeline,
    derive_provenance,
    source_provenance,
)


def write_channel(
    source, target, channel, checkpoint=lambda: None, parent_provenance=None
):
    parent_provenance = parent_provenance or source_provenance(source)
    if file_sha256(source) != parent_provenance["asset_sha256"]:
        raise ASRFailure("asset_integrity_failure")
    with wave.open(str(source), "rb") as audio:
        count = audio.getnchannels()
        if (
            not 1 <= count <= MAX_CHANNELS
            or not 0 <= channel < count
            or audio.getsampwidth() != 2
        ):
            raise ASRFailure("unsupported_asr_input")
        with wave.open(str(target), "wb") as output:
            output.setparams((1, 2, audio.getframerate(), 0, "NONE", "not compressed"))
            while data := audio.readframes(16000):
                checkpoint()
                # Copy exact little-endian PCM bytes, without mixing or quantizing.
                output.writeframes(memoryview(data).cast("h")[channel::count].tobytes())
            frame_count, sample_rate = audio.getnframes(), audio.getframerate()
    return derive_provenance(
        parent_provenance,
        target,
        "interleaved_pcm_channel_extract_v1",
        {
            "channel_index": channel,
            "source_channel_count": count,
            "source_sample_rate": sample_rate,
            "sample_format": "pcm_s16le",
            "mixing": False,
        },
        channel_timeline(channel, count, sample_rate, frame_count),
    )


def transcribe_channels(
    source, metadata, adapter, checkpoint, load_channel=None, save_channel=None
):
    outputs = []
    with tempfile.TemporaryDirectory(prefix="scribe-channels-") as directory:
        for channel in range(metadata["channels"]):
            target = Path(directory) / "channel.wav"
            channel_provenance = write_channel(
                source,
                target,
                channel,
                checkpoint,
                metadata.get("audio_provenance"),
            )
            mono = {**metadata, **inspect_pcm_wav(target)}
            mono["audio_provenance"] = channel_provenance
            # A failed channel fails the job; never silently publish partial coverage.
            pcm_hash = file_sha256(target)
            output = load_channel(channel, pcm_hash) if load_channel else None
            if output is None:
                output = adapter.transcribe(target, mono, checkpoint)
                if isinstance(output, dict):
                    output["isolated_channel_pcm_sha256"] = pcm_hash
                    output["audio_provenance"] = channel_provenance
                if save_channel:
                    save_channel(channel, output)
            if isinstance(output, dict):
                output["isolated_channel_pcm_sha256"] = pcm_hash
                output["audio_provenance"] = channel_provenance
            outputs.append(output)
            checkpoint()
    return {"channel_outputs": outputs}


def build_channels(
    raw, metadata, encounter_id, upload_id, profile, transcript_id, version
):
    outputs = raw["channel_outputs"]
    if len(outputs) != metadata["channels"]:
        raise ASRFailure("invalid_asr_output")
    body, segments, channels = None, [], []
    for index, output in enumerate(outputs):
        item = build_transcript(
            output, metadata, encounter_id, upload_id, profile, transcript_id, version
        )
        item["provenance"]["isolated_channel_pcm_sha256"] = output.get(
            "isolated_channel_pcm_sha256"
        )
        item["provenance"]["derived_audio_provenance"] = output.get(
            "audio_provenance"
        )
        body = body or deepcopy(item)
        for segment in item["segments"]:
            segment.update(channel_index=index, speaker_id=f"channel_{index}")
            segment["uncertainties"].append("channel_is_not_verified_speaker")
        segments.extend(item["segments"])
        channels.append(
            {
                "channel_index": index,
                "speaker_id": f"channel_{index}",
                "untranscribed_intervals": item["untranscribed_intervals"],
                "provenance": item["provenance"],
                "review_flags": item["review_flags"],
            }
        )
    if len(segments) > 10000 or sum(len(s["text"]) for s in segments) > 500000:
        raise ASRFailure("invalid_asr_output")
    body["segments"] = sorted(
        segments, key=lambda s: (s["start_ms"], s["channel_index"], s["end_ms"])
    )
    body["channels"] = channels
    body["untranscribed_intervals"] = [
        {**gap, "channel_index": c["channel_index"]}
        for c in channels
        for gap in c["untranscribed_intervals"]
    ]
    body["review_flags"] = sorted(
        set(flag for c in channels for flag in c["review_flags"])
        | {"channel_roles_require_confirmation", "cross_talk_requires_review"}
    )
    if segments:
        body["review_flags"] = [
            flag
            for flag in body["review_flags"]
            if flag not in {"no_transcribed_speech", "digital_silence"}
        ]
    if not all("digital_silence" in c["review_flags"] for c in channels):
        body["review_flags"] = [
            flag for flag in body["review_flags"] if flag != "digital_silence"
        ]
    body["provenance"].pop("isolated_channel_pcm_sha256", None)
    body["provenance"]["inference_executed"] = any(
        c["provenance"]["inference_executed"] for c in channels
    )
    timings = [c["provenance"].get("timing", {}) for c in channels]
    body["provenance"]["timing"] = {
        "channel_count": len(channels),
        "cached_channels": sum(t.get("model_cache_hit") is True for t in timings),
        "summed_model_load_seconds": sum(
            t.get("model_load_seconds", 0) for t in timings
        ),
        "summed_channel_inference_seconds": sum(
            t.get("inference_seconds", 0) for t in timings
        ),
    }
    body["provenance"]["preprocessing"] = "independent_pcm_channels_shared_timeline_v2"
    body["diarization"] = {
        "method": "physical_channels_not_speaker_identification",
        "clinical_validation": "not_validated",
        "role_assignment": "clinician_confirmation_required",
        "segments": [
            {
                k: s[k]
                for k in (
                    "start_ms",
                    "end_ms",
                    "speaker_id",
                    "role",
                    "role_status",
                    "channel_index",
                )
            }
            for s in body["segments"]
        ],
    }
    return body
