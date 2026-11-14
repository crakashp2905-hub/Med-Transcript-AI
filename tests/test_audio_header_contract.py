"""Declared PCM/WAV dimensions are checked before ingest publishes a result."""

import wave
import struct
import tracemalloc

import pytest

from services.api.ingest import MAX_UPLOAD_BYTES, InvalidAudio, inspect_pcm_wav


def make_wav(path, *, channels=1, sample_rate=16000, sample_width=2, frames=32):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(sample_width)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\0" * frames * channels * sample_width)
    return bytearray(path.read_bytes())


@pytest.mark.parametrize("channels", [1, 2, 8])
@pytest.mark.parametrize("sample_rate", [8000, 16000, 48000])
def test_pcm_wav_declared_channel_and_rate_dimensions_are_read(
    tmp_path, channels, sample_rate
):
    source = tmp_path / "dimensions.wav"
    make_wav(source, channels=channels, sample_rate=sample_rate)

    inspected = inspect_pcm_wav(source)

    assert inspected["codec"] == "pcm_s16le"
    assert inspected["channels"] == channels
    assert inspected["sample_rate"] == sample_rate
    assert inspected["frames"] == 32
    assert inspected["bytes"] == source.stat().st_size


@pytest.mark.parametrize(
    ("offset", "value", "code"),
    [
        pytest.param(
            22, (0).to_bytes(2, "little"), "unsupported_media", id="zero-channels"
        ),
        pytest.param(
            22, (9).to_bytes(2, "little"), "unsupported_media", id="too-many-channels"
        ),
        pytest.param(
            24, (7999).to_bytes(4, "little"), "unsupported_media", id="rate-below-bound"
        ),
        pytest.param(
            24,
            (48001).to_bytes(4, "little"),
            "unsupported_media",
            id="rate-above-bound",
        ),
        pytest.param(
            28, (2).to_bytes(4, "little"), "invalid_media", id="forged-byte-rate"
        ),
        pytest.param(
            32, (1).to_bytes(2, "little"), "invalid_media", id="forged-block-alignment"
        ),
        pytest.param(
            34,
            (24).to_bytes(2, "little"),
            "unsupported_media",
            id="unsupported-sample-width",
        ),
        pytest.param(
            40, (63).to_bytes(4, "little"), "invalid_media", id="partial-frame"
        ),
    ],
)
def test_forged_pcm_wav_dimensions_fail_closed(tmp_path, offset, value, code):
    source = tmp_path / "forged.wav"
    body = make_wav(source)
    body[offset : offset + len(value)] = value
    source.write_bytes(body)

    with pytest.raises(InvalidAudio, match=code):
        inspect_pcm_wav(source)


def test_zero_frame_recording_is_rejected(tmp_path):
    source = tmp_path / "empty-audio.wav"
    make_wav(source, frames=0)
    with pytest.raises(InvalidAudio, match="invalid_media"):
        inspect_pcm_wav(source)


def test_overlong_sparse_recording_is_rejected_before_audio_read(tmp_path):
    source = tmp_path / "overlong.wav"
    body = make_wav(source, frames=1)
    data_bytes = (16000 * 3600 + 1) * 2
    struct.pack_into("<I", body, 4, 36 + data_bytes)
    struct.pack_into("<I", body, 40, data_bytes)
    source.write_bytes(body)
    with source.open("r+b") as target:
        target.truncate(44 + data_bytes)

    with pytest.raises(InvalidAudio, match="duration_limit_exceeded"):
        inspect_pcm_wav(source)


def test_maximum_permitted_sparse_upload_stays_within_small_memory_cap(tmp_path):
    source = tmp_path / "maximum-size.wav"
    body = make_wav(source, frames=32)
    junk_bytes = MAX_UPLOAD_BYTES - len(body) - 8
    assert junk_bytes % 2 == 0
    struct.pack_into("<I", body, 4, MAX_UPLOAD_BYTES - 8)
    source.write_bytes(body + b"JUNK" + struct.pack("<I", junk_bytes))
    with source.open("r+b") as target:
        target.truncate(MAX_UPLOAD_BYTES)

    tracemalloc.start()
    try:
        inspected = inspect_pcm_wav(source)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert source.stat().st_size == MAX_UPLOAD_BYTES
    assert inspected["frames"] == 32
    assert peak < 8 * 1024 * 1024
