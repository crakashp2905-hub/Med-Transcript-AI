"""Bounded-memory checks for the largest supported physical recording shape."""

import hashlib
import struct
import time
import tracemalloc

import pytest

from services.api.ingest import InvalidAudio, file_sha256, inspect_pcm_wav


def _sparse_pcm_wav(path, *, channels, sample_rate, frames):
    data_bytes = channels * 2 * frames
    with path.open("wb") as output:
        output.write(b"RIFF" + struct.pack("<I", 36 + data_bytes) + b"WAVE")
        output.write(b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate,
                                             sample_rate * channels * 2,
                                             channels * 2, 16))
        output.write(b"data" + struct.pack("<I", data_bytes))
        output.seek(44 + data_bytes - 1)
        output.write(b"\0")


def test_maximum_supported_multichannel_audio_uses_bounded_python_memory(tmp_path):
    # 30 minutes of 16 kHz, 8-channel PCM is 460.8 MB, near the 512 MB cap.
    path = tmp_path / "maximum-multichannel.wav"
    frames = 16000 * 30 * 60
    _sparse_pcm_wav(path, channels=8, sample_rate=16000, frames=frames)

    tracemalloc.start()
    started = time.perf_counter()
    metadata = inspect_pcm_wav(path)
    digest = file_sha256(path)
    elapsed = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert metadata["channels"] == 8
    assert metadata["duration_ms"] == 30 * 60 * 1000
    assert metadata["bytes"] == 44 + frames * 8 * 2
    with path.open("rb") as audio:
        assert digest == hashlib.file_digest(audio, "sha256").hexdigest()
    assert peak_bytes < 8 * 1024 * 1024
    assert elapsed < 120


@pytest.mark.parametrize(
    ("channels", "sample_rate", "frames", "message"),
    [
        (1, 16000, 16000 * 3601, "duration_limit_exceeded"),
    ],
)
def test_oversized_duration_is_rejected_without_reading_pcm(
    tmp_path, channels, sample_rate, frames, message
):
    path = tmp_path / "over-duration.wav"
    _sparse_pcm_wav(path, channels=channels, sample_rate=sample_rate, frames=frames)
    with pytest.raises(InvalidAudio, match=message):
        inspect_pcm_wav(path)


def test_file_over_the_byte_cap_is_rejected_from_size_before_payload_read(tmp_path):
    path = tmp_path / "over-byte-cap.wav"
    with path.open("wb") as output:
        output.write(b"RIFF" + struct.pack("<I", 512_000_000 - 8) + b"WAVE")
        output.seek(512_000_000)
        output.write(b"\0")
    with pytest.raises(InvalidAudio, match="invalid_media"):
        inspect_pcm_wav(path)
