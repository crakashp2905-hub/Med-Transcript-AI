"""Bounded-memory checks for the largest supported physical recording shape."""

import hashlib
import json
import shutil
import struct
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor

import pytest

from services.api.ingest import InvalidAudio, file_sha256, inspect_pcm_wav


def _sparse_pcm_wav(path, *, channels, sample_rate, frames):
    data_bytes = channels * 2 * frames
    with path.open("wb") as output:
        output.write(b"RIFF" + struct.pack("<I", 36 + data_bytes) + b"WAVE")
        output.write(
            b"fmt "
            + struct.pack(
                "<IHHIIHH",
                16,
                1,
                channels,
                sample_rate,
                sample_rate * channels * 2,
                channels * 2,
                16,
            )
        )
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


def test_concurrent_long_recording_intake_preserves_failures_and_resource_trace(
    tmp_path,
):
    valid = tmp_path / "long-form-30m-8ch.wav"
    invalid = tmp_path / "over-byte-cap.wav"
    _sparse_pcm_wav(
        valid, channels=8, sample_rate=16000, frames=16000 * 30 * 60
    )
    with invalid.open("wb") as output:
        output.write(b"RIFF" + struct.pack("<I", 512_000_000 - 8) + b"WAVE")
        output.seek(512_000_000)
        output.write(b"\0")

    disk_before = shutil.disk_usage(tmp_path)
    tracemalloc.start()
    started, cpu_started = time.perf_counter(), time.process_time()

    def process(path):
        try:
            metadata = inspect_pcm_wav(path)
            return {
                "status": "succeeded",
                "sha256": file_sha256(path),
                "duration_ms": metadata["duration_ms"],
                "bytes": metadata["bytes"],
            }
        except InvalidAudio as error:
            return {"status": "failed", "error_code": str(error)}

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(process, [valid, valid, invalid]))
    elapsed = time.perf_counter() - started
    cpu_seconds = time.process_time() - cpu_started
    _, peak_python_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    disk_after = shutil.disk_usage(tmp_path)

    assert [row["status"] for row in results] == [
        "succeeded",
        "succeeded",
        "failed",
    ]
    assert results[0]["sha256"] == results[1]["sha256"]
    assert results[0]["duration_ms"] == 30 * 60 * 1000
    assert results[2]["error_code"] == "invalid_media"
    assert peak_python_bytes < 16 * 1024 * 1024
    assert elapsed < 120
    print(
        json.dumps(
            {
                "scenario": "concurrent_synthetic_long_recording_intake",
                "valid_recordings": 2,
                "failed_recordings": 1,
                "preserved_failures": [results[2]["error_code"]],
                "duration_ms": results[0]["duration_ms"],
                "per_recording_bytes": results[0]["bytes"],
                "elapsed_seconds": round(elapsed, 6),
                "process_cpu_seconds": round(cpu_seconds, 6),
                "peak_python_allocation_bytes": peak_python_bytes,
                "logical_fixture_bytes": valid.stat().st_size + invalid.stat().st_size,
                "disk_free_before_bytes": disk_before.free,
                "disk_free_after_bytes": disk_after.free,
            },
            sort_keys=True,
        )
    )
