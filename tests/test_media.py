import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import wave

import pytest

from services.api.ingest import inspect_pcm_wav, run_once
from services.media_decoder import normalize
from tests.test_foundation import queue_upload, headers


def stereo_wav():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as target:
        target.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
        target.writeframes(b"\1\0\1\0" * 4800)
    return buffer.getvalue()


def test_separate_decoder_normalizes_stereo_48k(tmp_path):
    pytest.importorskip("av")
    source, target = tmp_path / "source.wav", tmp_path / "normalized.wav"
    source.write_bytes(stereo_wav())
    original = source.read_bytes()
    result = normalize(source, target, "audio/wav")
    assert result["error_code"] is None, result
    assert source.read_bytes() == original
    assert (
        result["audio_provenance"]["parent_sha256"]
        == hashlib.sha256(original).hexdigest()
    )
    assert target.read_bytes() != original
    metadata = inspect_pcm_wav(target)
    assert metadata["channels"] == 2 and metadata["sample_rate"] == 16000
    assert metadata["duration_ms"] == 100


def test_ingest_publishes_normalized_asset_after_authorization_check(setup):
    pytest.importorskip("av")
    client, db, _ = setup
    original = stereo_wav()
    eid, upload, _, queued = queue_upload(client, original)
    root = Path(db).parent / "assets"
    assert run_once(db, str(root))["status"] == "succeeded"
    result = client.get(queued["status_url"], headers=headers()).json()["result"]
    assert result["asr_sample_rate"] == 16000
    original_path = root / f"{upload['id']}.wav"
    normalized_path = root / f"{upload['id']}.normalized.wav"
    assert original_path.read_bytes() == original
    assert hashlib.sha256(original).hexdigest() == result["sha256"]
    assert result["audio_provenance"]["parent_sha256"] == result["sha256"]
    assert normalized_path.is_file() and normalized_path.read_bytes() != original
    assert not list(root.glob("*.*.normalized.wav"))


def test_declared_type_mismatch_is_rejected(tmp_path):
    pytest.importorskip("av")
    source, target = tmp_path / "source.wav", tmp_path / "normalized.wav"
    source.write_bytes(stereo_wav())
    assert (
        normalize(source, target, "audio/mpeg")["error_code"] == "media_type_mismatch"
    )


def test_normalizer_keeps_original_bytes_and_links_distinct_output(
    tmp_path, monkeypatch
):
    import services.media_decoder as decoder

    source, target = tmp_path / "source.wav", tmp_path / "normalized.wav"
    original = stereo_wav()
    source.write_bytes(original)

    def synthetic_child(command, **kwargs):
        destination = Path(command[command.index("--destination") + 1])
        with wave.open(str(destination), "wb") as output:
            output.setparams((2, 2, 16000, 0, "NONE", "not compressed"))
            output.writeframes(b"\0\0\0\0" * 1600)
        response = {
            "frames": 1600,
            "error_code": None,
            "source_sample_rate": 48000,
            "source_channels": 2,
            "source_origin_ms": None,
            "source_container": "wav",
            "output_sample_rate": 16000,
            "output_channels": 2,
            "output_encoding": "pcm_s16le",
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(response).encode())

    monkeypatch.setattr(decoder.subprocess, "run", synthetic_child)
    result = normalize(source, target, "audio/wav")

    digest = hashlib.sha256(original).hexdigest()
    assert result["error_code"] is None
    assert source.read_bytes() == original
    assert target.is_file() and target.read_bytes() != original
    assert result["audio_provenance"]["parent_sha256"] == digest
    assert (
        result["audio_provenance"]["asset_sha256"]
        == hashlib.sha256(target.read_bytes()).hexdigest()
    )


def test_normalizer_rejects_changed_original_after_child_returns(tmp_path, monkeypatch):
    import services.media_decoder as decoder

    source, target = tmp_path / "source.wav", tmp_path / "normalized.wav"
    source.write_bytes(stereo_wav())

    def mutating_child(command, **kwargs):
        path = Path(command[command.index("--source") + 1])
        path.write_bytes(path.read_bytes() + b"changed")
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "frames": 1600,
                    "error_code": None,
                    "source_sample_rate": 48000,
                    "source_channels": 2,
                    "source_origin_ms": None,
                    "source_container": "wav",
                    "output_sample_rate": 16000,
                    "output_channels": 2,
                    "output_encoding": "pcm_s16le",
                }
            ).encode(),
        )

    monkeypatch.setattr(decoder.subprocess, "run", mutating_child)
    assert normalize(source, target, "audio/wav")["error_code"] == (
        "source_audio_changed_during_normalization"
    )


def test_ingest_keeps_original_and_publishes_hash_linked_working_copy(
    setup, monkeypatch
):
    from services.audio_provenance import (
        derive_provenance,
        normalization_timeline,
        source_provenance,
    )

    client, db, _ = setup
    original = stereo_wav()
    encounter, upload, _, queued = queue_upload(client, original)
    root = Path(db).parent / "assets"

    def scripted_normalize(source, destination, media_type):
        with wave.open(str(destination), "wb") as output:
            output.setparams((2, 2, 16000, 0, "NONE", "not compressed"))
            output.writeframes(b"\0\0\0\0" * 1600)
        parent = source_provenance(source, media_type)
        return {
            "frames": 1600,
            "error_code": None,
            "source_sample_rate": 48000,
            "source_channels": 2,
            "source_origin_ms": None,
            "source_container": "wav",
            "output_sample_rate": 16000,
            "output_channels": 2,
            "output_encoding": "pcm_s16le",
            "audio_provenance": derive_provenance(
                parent,
                destination,
                "scripted_test_resample_v1",
                {"source_sample_rate": 48000, "output_sample_rate": 16000},
                normalization_timeline(48000, 16000),
            ),
        }

    monkeypatch.setattr("services.media_decoder.normalize", scripted_normalize)
    assert run_once(db, str(root))["status"] == "succeeded"

    source = root / f"{upload['id']}.wav"
    working = root / f"{upload['id']}.normalized.wav"
    result = client.get(queued["status_url"], headers=headers()).json()["result"]
    original_sha = hashlib.sha256(original).hexdigest()
    assert source.read_bytes() == original
    assert (
        working.is_file()
        and hashlib.sha256(working.read_bytes()).hexdigest()
        == (result["working_sha256"])
    )
    assert (
        result["sha256"] == result["audio_provenance"]["parent_sha256"] == original_sha
    )
    assert result["working_sha256"] == result["audio_provenance"]["asset_sha256"]
