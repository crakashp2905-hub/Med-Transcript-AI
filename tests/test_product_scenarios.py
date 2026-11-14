import hashlib
import json
import wave
from pathlib import Path

from services.product_scenarios import build_scenarios


def test_offline_scenarios_cover_all_requested_conditions_and_bind_local_sources(
    tmp_path,
):
    output = tmp_path / "scenarios"
    document = build_scenarios(".", output)
    assert document["scenario_count"] == 5
    assert {scenario["scenario_type"] for scenario in document["scenarios"]} == {
        "short",
        "noisy",
        "overlapping",
        "medication_heavy",
        "multi_speaker",
    }
    assert document["generated_from_local_assets_only"] is True
    assert document["clinical_acceptance"] is False
    assert document["clinical_release_authorized"] is False

    for scenario in document["scenarios"]:
        assert scenario["clinical_acceptance"] is False
        assert scenario["clinical_release_authorized"] is False
        if "audio_asset" in scenario:
            asset = output / scenario["audio_asset"]
            assert (
                hashlib.sha256(asset.read_bytes()).hexdigest()
                == scenario["audio_sha256"]
            )
            with wave.open(str(asset), "rb") as audio:
                assert audio.getframerate() == 16000
                assert audio.getnchannels() == scenario["channels"]
                assert audio.getsampwidth() == 2
                assert (
                    audio.getnframes() * 1000 // audio.getframerate()
                    == scenario["duration_ms"]
                )
            for turn in scenario["transcript_turns"]:
                source = Path("evaluation/datasets/primock57-expanded-v1") / next(
                    item["audio"]
                    for item in json.loads(
                        Path(
                            "evaluation/datasets/primock57-expanded-v1/manifest.json"
                        ).read_text(encoding="utf-8")
                    )["samples"]
                    if item["sample_id"] == turn["source_sample_id"]
                )
                assert (
                    hashlib.sha256(source.read_bytes()).hexdigest()
                    == turn["source_audio_sha256"]
                )

    overlap = next(
        scenario
        for scenario in document["scenarios"]
        if scenario["scenario_type"] == "overlapping"
    )
    assert overlap["audio_transform"]["overlap_ms"] > 0
    two_channel = next(
        scenario
        for scenario in document["scenarios"]
        if scenario["scenario_type"] == "multi_speaker"
    )
    assert two_channel["channels"] == 2
    assert two_channel["speaker_roles_are_reference_only"] is True

    medication = next(
        scenario
        for scenario in document["scenarios"]
        if scenario["scenario_type"] == "medication_heavy"
    )
    assert medication["input_mode"] == "typed_synthetic_script_no_audio"
    assert "audio_asset" not in medication
    assert len(medication["synthetic_script"]["review_targets"]) == 4


def test_scenario_generation_is_byte_deterministic_for_same_local_inputs(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_manifest = build_scenarios(".", first)
    second_manifest = build_scenarios(".", second)
    assert first_manifest == second_manifest
    assert (first / "manifest.json").read_bytes() == (
        second / "manifest.json"
    ).read_bytes()
    for scenario in first_manifest["scenarios"]:
        if "audio_asset" in scenario:
            assert (first / scenario["audio_asset"]).read_bytes() == (
                second / scenario["audio_asset"]
            ).read_bytes()


def test_checked_in_scenario_assets_match_local_regeneration(tmp_path):
    regenerated = tmp_path / "regenerated"
    document = build_scenarios(".", regenerated)
    checked_in = Path("evaluation/scenarios/offline-encounters-v1")
    assert (regenerated / "manifest.json").read_bytes() == (
        checked_in / "manifest.json"
    ).read_bytes()
    for scenario in document["scenarios"]:
        if "audio_asset" in scenario:
            assert (regenerated / scenario["audio_asset"]).read_bytes() == (
                checked_in / scenario["audio_asset"]
            ).read_bytes()
