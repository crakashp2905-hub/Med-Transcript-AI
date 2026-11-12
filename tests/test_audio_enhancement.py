import shutil
import wave

import pytest

pytest.importorskip("numpy")

import numpy as np

from services.audio_enhancement import (
    highpass_transform,
    normalize_rms_transform,
    prepare_candidate,
    spectral_gate_transform,
)
from services.audio_provenance import validate_provenance


def make_wav(path):
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        output.writeframes(b"\x10\x00" * 32)


TIMELINE = {"kind": "same_rate_filter", "status": "sample_clock_preserved"}


def test_disabled_candidate_uses_exact_original_path_and_bytes(tmp_path):
    source = tmp_path / "original.wav"
    make_wav(source)
    original = source.read_bytes()

    candidate = prepare_candidate(source)

    assert candidate["candidate_path"] == str(source.resolve())
    assert candidate["candidate_sha256"]
    assert candidate["enhancement_applied"] is False
    assert (
        candidate["audio_provenance"]["asset_sha256"] == candidate["candidate_sha256"]
    )
    assert source.read_bytes() == original
    assert list(tmp_path.iterdir()) == [source]


def test_enabled_candidate_uses_new_file_and_keeps_original_unchanged(tmp_path):
    source, output = tmp_path / "original.wav", tmp_path / "candidate.wav"
    make_wav(source)
    original = source.read_bytes()

    result = prepare_candidate(
        source,
        output,
        "test_gain_candidate_v1",
        lambda input_path, output_path: shutil.copyfile(input_path, output_path),
        {"gain_db": 0},
        TIMELINE,
    )

    assert result["enhancement_applied"] is True
    assert result["source_sha256"] == result["audio_provenance"]["parent_sha256"]
    assert result["candidate_sha256"] == result["source_sha256"]
    assert validate_provenance(result["audio_provenance"])
    assert output.read_bytes() == original
    assert source.read_bytes() == original
    assert not list(tmp_path.glob(".audio-*-*"))


def test_failed_transform_cannot_modify_source_or_publish_candidate(tmp_path):
    source, output = tmp_path / "original.wav", tmp_path / "candidate.wav"
    make_wav(source)
    original = source.read_bytes()

    def corrupt_snapshot(input_path, output_path):
        input_path.write_bytes(b"corrupt")
        output_path.write_bytes(b"partial")

    with pytest.raises(ValueError, match="enhancement_input_snapshot_changed"):
        prepare_candidate(
            source,
            output,
            "test_bad_transform_v1",
            corrupt_snapshot,
            {},
            TIMELINE,
        )
    assert source.read_bytes() == original
    assert not output.exists()
    assert not list(tmp_path.glob(".audio-*-*"))


def test_rms_candidate_reaches_target_without_clipping(tmp_path):
    source, output = tmp_path / "quiet.wav", tmp_path / "normalized.wav"
    values = np.full(16000, 5000, dtype="<i2")
    with wave.open(str(source), "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(values.tobytes())
    original = source.read_bytes()

    normalize_rms_transform(-23, 0.98)(source, output)

    with wave.open(str(output), "rb") as audio:
        result = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2")
    rms_dbfs = 20 * np.log10(np.sqrt(np.mean(result.astype(np.float64) ** 2)) / 32768)
    assert rms_dbfs == pytest.approx(-23, abs=0.01)
    assert int(np.max(np.abs(result))) < 32760
    assert source.read_bytes() == original


def test_highpass_and_spectral_candidates_preserve_frame_count(tmp_path):
    pytest.importorskip("scipy")
    source = tmp_path / "mixed.wav"
    rate, count = 16000, 16000
    time = np.arange(count) / rate
    values = (
        3000
        + 7000 * np.sin(2 * np.pi * 50 * time)
        + 3000 * np.sin(2 * np.pi * 500 * time)
    )
    with wave.open(str(source), "wb") as audio:
        audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        audio.writeframes(np.clip(values, -32768, 32767).astype("<i2").tobytes())
    original = source.read_bytes()
    highpass, spectral = tmp_path / "highpass.wav", tmp_path / "spectral.wav"

    highpass_transform(80, 4)(source, highpass)
    spectral_gate_transform(25, 1.5, 0.15)(source, spectral)

    with wave.open(str(highpass), "rb") as audio:
        assert audio.getnframes() == count
        highpassed = np.frombuffer(audio.readframes(count), dtype="<i2")
    with wave.open(str(spectral), "rb") as audio:
        assert audio.getnframes() == count
        gated = np.frombuffer(audio.readframes(count), dtype="<i2")
    assert np.isfinite(highpassed).all() and np.isfinite(gated).all()
    assert source.read_bytes() == original
    assert highpass.read_bytes() != original
    assert spectral.read_bytes() != original
