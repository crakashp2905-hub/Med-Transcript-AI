import wave
from types import SimpleNamespace

from services.asr.transcripts import build_transcript
from services.audio_provenance import (
    channel_timeline,
    crop_timeline,
    derive_provenance,
    source_provenance_from_digest,
)


PROFILE = SimpleNamespace(
    engine="faster-whisper",
    runtime_version="1",
    sha256="a" * 64,
    profile_id="fixture",
    source="local",
    revision="r",
    artifacts=[],
)


def _source(channels=1):
    return source_provenance_from_digest(
        "b" * 64,
        {
            "container": "wav",
            "encoding": "pcm_s16le",
            "channels": channels,
            "sample_rate": 16000,
            "frames": 32000,
            "duration_seconds": 2,
        },
        "audio/wav",
    )


def _mono_wav(path, frames):
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        output.writeframes(b"\0\0" * frames)


def _transcribe(metadata, start=0.25, end=0.5):
    return build_transcript(
        {
            "duration_seconds": metadata["duration_ms"] / 1000,
            "segments": [{"start_seconds": start, "end_seconds": end, "text": "hello"}],
        },
        metadata,
        "encounter",
        "upload",
        PROFILE,
        "transcript",
        1,
    )["segments"][0]


def test_native_segments_map_to_stable_original_pcm_source_windows():
    metadata = {
        "duration_ms": 2000,
        "sha256": "b" * 64,
        "audio_provenance": _source(),
        "timeline_mapping_status": "original_pcm_timeline",
    }
    first = _transcribe(metadata)
    again = _transcribe(metadata)
    assert first["source_mapping_status"] == "mapped_same_rate_sample_index"
    assert first["source_window_id"] == again["source_window_id"]
    assert first["source_audio_sha256"] == "b" * 64
    assert first["source_window_start_frame"] == 0
    assert first["source_window_end_frame_exclusive"] == 32000
    assert first["source_start_frame"] == 4000
    assert first["source_end_frame_exclusive"] == 8000
    assert first["source_channel_index"] is None


def test_channel_and_crop_provenance_maps_segment_back_to_original_frames(tmp_path):
    root = _source(channels=2)
    channel_path = tmp_path / "channel.wav"
    _mono_wav(channel_path, 32000)
    channel = derive_provenance(
        root,
        channel_path,
        "interleaved_pcm_channel_extract_v1",
        {"channel_index": 1},
        channel_timeline(1, 2, 16000, 32000),
    )
    crop_path = tmp_path / "crop.wav"
    _mono_wav(crop_path, 8000)
    timeline = crop_timeline(1600, 9600, 16000)
    timeline.update(
        kind="channel_crop_sample_index_offset",
        channel_index=1,
        source_channel_count=2,
    )
    crop = derive_provenance(
        channel,
        crop_path,
        "bounded_retranscription_crop_v1",
        {"start_ms": 100, "end_ms": 600},
        timeline,
    )
    segment = _transcribe(
        {
            "duration_ms": 500,
            "sha256": "b" * 64,
            "audio_provenance": crop,
            "timeline_mapping_status": "original_pcm_timeline",
        },
        start=0.125,
        end=0.25,
    )
    assert segment["source_mapping_status"] == "mapped_same_rate_sample_index"
    assert segment["source_window_start_frame"] == 1600
    assert segment["source_window_end_frame_exclusive"] == 9600
    assert segment["source_start_frame"] == 3600
    assert segment["source_end_frame_exclusive"] == 5600
    assert segment["source_channel_index"] == 1


def test_unmeasured_resampling_does_not_publish_source_frame_bounds():
    segment = _transcribe(
        {
            "duration_ms": 2000,
            "sha256": "b" * 64,
            "audio_provenance": _source(),
            "timeline_mapping_status": "decoded_media_requires_review",
        }
    )
    assert segment["source_mapping_status"] == "source_timeline_unverified"
    assert "source_start_frame" not in segment
    assert "source_end_frame_exclusive" not in segment
