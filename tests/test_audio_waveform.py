import hashlib
import struct
import wave
from pathlib import Path

import pytest

from services.audio_waveform import waveform
from services.api.ingest import run_once as ingest_once
from tests.test_foundation import headers, queue_upload, wav_bytes


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
        target.writeframes(b"".join(struct.pack("<hh", *frame) for frame in frames))


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
    assert all_channels["peaks"] == [
        max(left["peaks"][0], right["peaks"][0]),
        max(left["peaks"][1], right["peaks"][1]),
    ]
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


def test_encounter_waveform_endpoint_serves_ingested_source_peaks(setup):
    client, db, _ = setup
    source = wav_bytes()
    encounter_id, upload, _, _ = queue_upload(client, source)
    assets = Path(db).parent / "assets"
    assert ingest_once(db, str(assets))["status"] == "succeeded"

    response = client.get(
        f"/v1/encounters/{encounter_id}/audio/{upload['id']}/waveform",
        headers=headers(),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["schema_version"] == "source_waveform_v1"
    assert result["source_sha256"] == hashlib.sha256(source).hexdigest()
    assert len(result["peaks"]) == 160
    assert all(0 <= peak <= 1 for peak in result["peaks"])
