import hashlib
import json
import wave
from pathlib import Path

import pytest

from services.asr.evaluation_contract import (
    make_contract,
    observed_channel_map,
    validate_contract,
    validate_manifest,
)
from services.api.ingest import file_sha256
from services.evaluation import run


class Profile:
    profile_id = "fixture"
    revision = "a" * 40
    sha256 = "b" * 64
    engine = "faster-whisper"
    runtime_version = "1.2.1"
    beam_size = 5

    def verify_artifacts(self):
        return None


def manifest_for(audio_sha256):
    return {
        "dataset_id": "fixture-v1",
        "split_role": "development_mechanistic",
        "data_class": "synthetic",
        "rights_reviewed": True,
        "license_id": "developer-fixture",
        "source_revision": "f" * 40,
        "samples": [
            {
                "sample_id": "sample-1",
                "group_id": "consultation-1",
                "language": "en",
                "audio": "sample.wav",
                "audio_sha256": audio_sha256,
                "reference": "No fever.",
                "speaker_role": "patient",
            },
            {
                "sample_id": "sample-2",
                "group_id": "consultation-1",
                "language": "en",
                "audio": "sample.wav",
                "audio_sha256": "c" * 64,
                "reference": "Dose 0.5 mg.",
                "speaker_role": "unknown",
            },
        ],
    }


@pytest.mark.parametrize(
    "patch",
    [
        {"rights_reviewed": False},
        {"split_role": ""},
        {"license_id": None},
        {"source_revision": ""},
        {"samples": []},
    ],
)
def test_incomplete_evaluation_manifest_is_rejected(patch):
    manifest = manifest_for("d" * 64)
    manifest.update(patch)
    with pytest.raises(ValueError):
        validate_manifest(manifest)


def test_duplicate_case_missing_reference_bad_digest_and_role_are_rejected():
    for key, value in (
        ("sample_id", "sample-1"),
        ("group_id", ""),
        ("reference", None),
        ("audio_sha256", "not-a-digest"),
        ("speaker_role", "clinician-or-patient-guessed"),
        ("reference_uncertain", "maybe"),
    ):
        manifest = manifest_for("d" * 64)
        manifest["samples"][1][key] = value
        with pytest.raises(ValueError):
            validate_manifest(manifest)


def test_unknown_multichannel_roles_remain_unknown():
    assert observed_channel_map({"speaker_role": "patient"}, 2) == [
        {"channel_index": 0, "role": "unknown", "role_source": "unmapped"},
        {"channel_index": 1, "role": "unknown", "role_source": "unmapped"},
    ]


def test_existing_public_sample_manifests_satisfy_the_contract():
    for path in (
        Path("evaluation/datasets/primock57-smoke-v1/manifest.json"),
        Path("evaluation/datasets/primock57-expanded-v1/manifest.json"),
        Path("evaluation/datasets/primock57-validation-v1/manifest.json"),
    ):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert len(validate_manifest(manifest)) == len(manifest["samples"])


def test_contract_reconciles_group_source_model_channels_and_failure_denominator():
    manifest = manifest_for("d" * 64)
    good = manifest["samples"][0]
    failed = manifest["samples"][1]
    records = [
        {
            "sample_id": good["sample_id"],
            "group_id": good["group_id"],
            "audio_path": good["audio"],
            "audio_sha256": good["audio_sha256"],
            "audio_integrity_verified": True,
            "channel_count": 1,
            "channel_map": observed_channel_map(good, 1),
            "reference_sha256": hashlib.sha256(good["reference"].encode()).hexdigest(),
            "reference_words": 2,
            "status": "completed",
        },
        {
            "sample_id": failed["sample_id"],
            "group_id": failed["group_id"],
            "audio_path": failed["audio"],
            "audio_sha256": failed["audio_sha256"],
            "audio_integrity_verified": False,
            "channel_count": None,
            "channel_map": [],
            "reference_sha256": hashlib.sha256(
                failed["reference"].encode()
            ).hexdigest(),
            "reference_words": 3,
            "status": "failed",
        },
    ]
    contract = make_contract(
        manifest=manifest,
        manifest_sha256="e" * 64,
        profile=Profile(),
        recordings=records,
    )
    assert validate_contract(contract)
    assert contract["denominator"] == {
        "sample_count": 2,
        "reference_words": 5,
        "failed_samples": 1,
        "failure_policy": "empty_hypothesis_full_reference_deletions",
        "includes_every_predeclared_reference": True,
    }
    tampered = dict(contract)
    tampered["denominator"] = {**contract["denominator"], "failed_samples": 0}
    with pytest.raises(ValueError, match="failure_inclusive_denominator_mismatch"):
        validate_contract(tampered)


def test_evaluation_run_emits_contract_and_keeps_failed_reference_words(
    tmp_path, monkeypatch
):
    audio = tmp_path / "sample.wav"
    with wave.open(str(audio), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(b"\x00\x00" * 1600)
    manifest = manifest_for(file_sha256(audio))
    manifest["samples"][0]["reference_uncertain"] = True
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output_path = tmp_path / "result.json"
    calls = []

    class Adapter:
        def __init__(self, profile):
            pass

        def transcribe(self, path, metadata, checkpoint):
            calls.append(path.name)
            return {"segments": [], "duration_seconds": 0.1}

    monkeypatch.setattr("services.evaluation.FasterWhisperAdapter", Adapter)
    monkeypatch.setattr(
        "services.evaluation.build_transcript",
        lambda *args: {"segments": [{"text": "No fever."}]},
    )
    run(manifest_path, Profile(), output_path)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    contract = report["evaluation_contract"]
    assert validate_contract(contract)
    assert calls == ["sample.wav"]
    assert contract["model"]["revision"] == Profile.revision
    assert contract["recordings"][0]["channel_map"] == [
        {
            "channel_index": 0,
            "role": "patient",
            "role_source": "reference_role_annotation",
        }
    ]
    assert contract["denominator"]["reference_words"] == 5
    assert contract["denominator"]["failed_samples"] == 1
    assert report["reference_words"] == 5
    assert report["reference_uncertainty_analysis"][
        "primary_scoring_includes_all_reference_words"
    ]
    assert contract["recordings"][0]["reference_uncertain"] is True
    assert report["wer_gate"]["status"] == "fail"

    alternate_path = tmp_path / "result-with-uncertainty-strata.json"
    run(
        manifest_path,
        Profile(),
        alternate_path,
        reference_uncertainty_policy="all_words_with_uncertainty_strata_v1",
    )
    alternate = json.loads(alternate_path.read_text(encoding="utf-8"))
    assert alternate["reference_words"] == report["reference_words"]
    assert (
        alternate["evaluation_contract"]["contract_sha256"]
        != contract["contract_sha256"]
    )
    assert (
        alternate["reference_uncertainty_analysis"]["strata"]["uncertain"][
            "reference_words"
        ]
        == 2
    )

    with pytest.raises(FileExistsError, match="immutable"):
        run(manifest_path, Profile(), output_path)


def test_malformed_manifest_fails_before_model_admission_or_report(
    tmp_path, monkeypatch
):
    manifest = manifest_for("d" * 64)
    manifest["samples"][0].pop("group_id")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output_path = tmp_path / "result.json"

    def forbidden_model_call(*args):
        raise AssertionError("inference_must_not_start")

    monkeypatch.setattr(
        "services.evaluation.FasterWhisperAdapter", forbidden_model_call
    )
    with pytest.raises(ValueError, match="incomplete_evaluation_sample"):
        run(manifest_path, Profile(), output_path)
    assert not output_path.exists()
