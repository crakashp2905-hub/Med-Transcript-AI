import wave

import pytest

from services.audio_provenance import (
    channel_timeline,
    crop_timeline,
    derive_provenance,
    source_provenance,
    source_provenance_from_digest,
    validate_provenance,
)


def write_pcm(path, samples, channels=1, rate=16000):
    with wave.open(str(path), "wb") as output:
        output.setparams((channels, 2, rate, 0, "NONE", "not compressed"))
        output.writeframes(samples)


def test_derived_audio_receipt_binds_parent_manifest_and_timeline(tmp_path):
    source = tmp_path / "source.wav"
    crop = tmp_path / "crop.wav"
    write_pcm(source, b"\x01\x00" * 8)
    write_pcm(crop, b"\x01\x00" * 4)

    parent = source_provenance(source)
    receipt = derive_provenance(
        parent, crop, "test_crop_v1", {"start_frame": 2}, crop_timeline(2, 6, 16000)
    )

    assert validate_provenance(receipt)
    assert receipt["parent_sha256"] == parent["asset_sha256"]
    assert receipt["timeline_mapping"]["parent_start_frame"] == 2
    receipt["transformation_manifest"]["parameters"]["start_frame"] = 3
    with pytest.raises(ValueError, match="manifest_digest_mismatch"):
        validate_provenance(receipt)


def test_channel_mapping_is_explicit_and_validated(tmp_path):
    source = tmp_path / "stereo.wav"
    output = tmp_path / "mono.wav"
    write_pcm(source, b"\x01\x00\x02\x00" * 4, channels=2)
    write_pcm(output, b"\x01\x00" * 4)

    receipt = derive_provenance(
        source_provenance(source),
        output,
        "channel_extract_v1",
        {"channel_index": 0},
        channel_timeline(0, 2, 16000, 4),
    )
    assert validate_provenance(receipt)
    assert receipt["timeline_mapping"]["formula"] == (
        "parent_frame = output_frame; channel = channel_index"
    )


def test_receipt_supports_all_parents_of_a_mixed_waveform(tmp_path):
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    mixed = tmp_path / "mixed.wav"
    write_pcm(first, b"\x01\x00" * 4)
    write_pcm(second, b"\x02\x00" * 4)
    write_pcm(mixed, b"\x02\x00" * 4)
    parent_one, parent_two = source_provenance(first), source_provenance(second)
    flac_source = source_provenance_from_digest(
        "a" * 64,
        {
            "container": "flac",
            "encoding": "flac_lossless",
            "channels": 1,
            "sample_rate": 16000,
            "frames": 4,
            "duration_seconds": 0.00025,
        },
        "audio/flac",
    )
    assert validate_provenance(flac_source)
    receipt = derive_provenance(
        parent_one,
        mixed,
        "test_mix_v1",
        {"method": "mean"},
        {"kind": "shared_sample_index_timeline", "status": "exact"},
        additional_parents=[parent_two],
    )
    assert validate_provenance(receipt)
    assert receipt["additional_parent_sha256s"] == [parent_two["asset_sha256"]]
