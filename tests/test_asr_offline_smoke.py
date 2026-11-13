import json
from pathlib import Path

import pytest

from services.api.ingest import file_sha256
from services.asr.admission import evaluate_candidate_admission
from services.asr.offline_smoke import run_smoke
from services.asr.profiles import ASRProfile


def _profile(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    for name, content in {
        "model.bin": b"local fixture weights",
        "config.json": b"{}",
        "tokenizer.json": b"{}",
    }.items():
        (model / name).write_bytes(content)
    return ASRProfile(
        profile_id="test-local",
        model_dir=str(model),
        source="test fixture",
        revision="a" * 40,
        license_id="test-only",
        artifacts={
            name: file_sha256(model / name)
            for name in ("model.bin", "config.json", "tokenizer.json")
        },
    )


def _admission(profile, evidence):
    return {
        "schema_version": "offline_asr_admission_v1",
        "profile_id": profile.profile_id,
        "profile_sha256": profile.sha256,
        "evidence": evidence,
        "decision": evaluate_candidate_admission(profile.profile_id, evidence),
    }


def _inputs(tmp_path, profile, evidence):
    profiles = tmp_path / "profiles.json"
    profiles.write_text(json.dumps([profile.model_dump(mode="json")]), encoding="utf-8")
    admission = tmp_path / "admission.json"
    admission.write_text(json.dumps(_admission(profile, evidence)), encoding="utf-8")
    return profiles, admission


def _evidence(**updates):
    evidence = {
        "reference_words": 100,
        "normalized_edits": 0,
        "failed_samples": 0,
        "sample_count": 3,
        "source_timing_validated": True,
        "license_reviewed": True,
        "critical_safety_review": "passed",
        "matched_paired_evaluation": True,
        "all_frozen_cases_accounted": True,
        "fabricated_outcomes": 0,
    }
    evidence.update(updates)
    return evidence


def test_non_admitted_local_profile_never_starts_inference(tmp_path, monkeypatch):
    profile = _profile(tmp_path)
    profiles, admission = _inputs(tmp_path, profile, _evidence(normalized_edits=6))
    monkeypatch.setattr(
        "services.asr.offline_smoke.run_evaluation",
        lambda *args: pytest.fail("inference must not run"),
    )

    result = run_smoke(profiles, admission, tmp_path / "report.json")

    assert result["status"] == "skipped"
    assert result["reason_code"] == "profile_not_admitted"
    assert result["admission"]["status"] == "denied"


def test_missing_admission_reports_local_model_without_inference(tmp_path, monkeypatch):
    profile = _profile(tmp_path)
    profiles, _ = _inputs(tmp_path, profile, _evidence())
    monkeypatch.setattr(
        "services.asr.offline_smoke.run_evaluation",
        lambda *args: pytest.fail("inference must not run"),
    )

    result = run_smoke(
        profiles, None, tmp_path / "report.json", profile_id=profile.profile_id
    )

    assert result["status"] == "skipped"
    assert result["reason_code"] == "admission_record_missing"
    assert result["local_model_status"] == "available_not_admitted"
    assert result["automatic_download"] is False


def test_matching_admitted_digest_invokes_failure_inclusive_harness(
    tmp_path, monkeypatch
):
    profile = _profile(tmp_path)
    profiles, admission = _inputs(tmp_path, profile, _evidence())
    calls = []

    def fake_evaluate(manifest, selected_profile, output_path):
        calls.append((Path(manifest), selected_profile.profile_id, Path(output_path)))
        return {"failed_samples": 0, "sample_count": 3}

    monkeypatch.setattr("services.asr.offline_smoke.run_evaluation", fake_evaluate)
    output = tmp_path / "evaluation.json"

    result = run_smoke(profiles, admission, output)

    assert result["status"] == "completed"
    assert result["evaluation"]["failed_samples"] == 0
    assert len(calls) == 1
    assert calls[0][1] == profile.profile_id
    assert calls[0][0].name == "manifest.json"


def test_profile_digest_change_blocks_inference(tmp_path, monkeypatch):
    profile = _profile(tmp_path)
    profiles, admission = _inputs(tmp_path, profile, _evidence())
    record = json.loads(admission.read_text(encoding="utf-8"))
    record["profile_sha256"] = "0" * 64
    admission.write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(
        "services.asr.offline_smoke.run_evaluation",
        lambda *args: pytest.fail("inference must not run"),
    )

    result = run_smoke(profiles, admission, tmp_path / "report.json")

    assert result["status"] == "skipped"
    assert result["reason_code"] == "profile_digest_not_admitted"


def test_smoke_cannot_use_unfrozen_manifest(tmp_path):
    profile = _profile(tmp_path)
    profiles, admission = _inputs(tmp_path, profile, _evidence())
    alternate = tmp_path / "manifest.json"
    alternate.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="frozen_primock57"):
        run_smoke(profiles, admission, tmp_path / "report.json", alternate)
