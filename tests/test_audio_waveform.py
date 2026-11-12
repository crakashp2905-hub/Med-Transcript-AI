import hashlib
import struct
import wave

import pytest

from services.audio_waveform import waveform


def write_wav(path, channels=2):
    frames = [
        (1000, -2000),
        (-3000, 4000),
        (5000, -6000),
        (-7000, 8000),
    ] * 4
    with wave.open(str(path), "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(
            b"".join(struct.pack("<hh", *frame) for frame in frames)
        )


def test_waveform_is_source_bound_and_channel_selective(tmp_path):
    audio = tmp_path / "source.wav"
    write_wav(audio)
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()

    all_channels = waveform(audio, digest, bins=2)
    left = waveform(audio, digest, channel=0, bins=2)
    right = waveform(audio, digest, channel=1, bins=2)

    assert all_channels["source_sha256"] == digest
    assert all_channels["duration_ms"] == 1
    assert len(all_channels["peaks"]) == 2
    assert all_channels["peaks"] == [max(left["peaks"][0], right["peaks"][0]), max(left["peaks"][1], right["peaks"][1])]
    assert left["selected_channel"] == 0
    assert right["selected_channel"] == 1
    assert left["peaks"] != right["peaks"]


def test_waveform_rejects_wrong_hash_and_unavailable_channel(tmp_path):
    audio = tmp_path / "source.wav"
    write_wav(audio)
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="asset_integrity_failure"):
        waveform(audio, "0" * 64)
    with pytest.raises(ValueError, match="channel_unavailable"):
        waveform(audio, digest, channel=2)
