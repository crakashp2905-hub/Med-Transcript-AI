import shutil
import wave

import pytest

from services.audio_enhancement import prepare_candidate
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
