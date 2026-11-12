"""Bounded, source-hash-checked waveform summaries for review intervals."""

import hashlib
import sys
import wave
from array import array
from pathlib import Path


def waveform(path: Path, expected_sha256: str, channel: int | None = None, bins=160):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise ValueError("asset_integrity_failure")
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        rate = source.getframerate()
        width = source.getsampwidth()
        frames = source.getnframes()
        if (
            width != 2
            or channels < 1
            or channels > 8
            or rate < 8000
            or rate > 192000
            or frames < 1
            or frames > 3600 * rate
        ):
            raise ValueError("unsupported_waveform_audio")
        if channel is not None and channel >= channels:
            raise ValueError("channel_unavailable")
        count = min(max(1, bins), frames)
        peaks = []
        consumed = 0
        for index in range(count):
            end = (index + 1) * frames // count
            frame_count = end - consumed
            raw = source.readframes(frame_count)
            consumed = end
            samples = array("h")
            samples.frombytes(raw)
            if sys.byteorder != "little":
                samples.byteswap()
            if channel is None:
                peak = max((abs(value) for value in samples), default=0)
            else:
                peak = max(
                    (
                        abs(samples[position])
                        for position in range(channel, len(samples), channels)
                    ),
                    default=0,
                )
            peaks.append(peak / 32768)
    return {
        "schema_version": "source_waveform_v1",
        "source_sha256": expected_sha256,
        "duration_ms": round(frames * 1000 / rate),
        "sample_rate": rate,
        "channels": channels,
        "selected_channel": channel,
        "peaks": peaks,
    }
