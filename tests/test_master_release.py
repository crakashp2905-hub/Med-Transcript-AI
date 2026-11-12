import hashlib
import json

from services import status_report
from services.master_release import TIERS, assess


def test_synthetic_demo_cannot_promote_research_pilot_or_clinical_tiers():
    result = assess(current_demo_pass=True)
    assert tuple(result["tiers"]) == TIERS
    assert result["tiers"]["local_demo"]["status"] == "verified"
    assert result["tiers"]["engineering_verified"]["status"] == "not_established"
    assert result["tiers"]["research_supported"]["status"] == "not_established"
    assert result["tiers"]["pilot_candidate"]["status"] == "not_established"
    assert (
        result["tiers"]["clinical_approved"]["status"]
        == "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED"
    )
    assert result["real_patient_release_authorized"] is False


def test_even_complete_hypothetical_inputs_do_not_self_authorize_clinical_release():
    result = assess(
        current_demo_pass=True,
        exact_commit_ci_pass=True,
        independent_clinical_gold=True,
        asr_five_percent_gate_pass=True,
        institutional_pilot_signoff=True,
    )
    assert result["tiers"]["pilot_candidate"]["status"] == "verified"
    assert (
        result["tiers"]["clinical_approved"]["status"]
        == "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED"
    )
    assert result["real_patient_release_authorized"] is False


def test_readiness_report_rejects_stale_or_corrupt_saved_demo_receipt(
    tmp_path, monkeypatch
):
    (tmp_path / "evaluation/reports").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    (tmp_path / "evaluation/reports/engineering-task-status.json").write_text(
        json.dumps({"total": 247}), encoding="utf-8"
    )
    monkeypatch.setattr(
        status_report, "validate", lambda ledger, root: {"total": 247, "verified": 0}
    )
    monkeypatch.setattr(status_report, "inspect", lambda root: {"models": []})
    monkeypatch.setattr(
        status_report.subprocess, "check_output", lambda *args, **kwargs: "a" * 40
    )
    report = tmp_path / "evaluation/reports/acceptance.json"
    summary = tmp_path / "data/offline-acceptance-summary.json"

    def save(commit):
        report.write_text(
            json.dumps(
                {
                    "source_commit": commit,
                    "checks": {
                        "synthetic_walkthrough": {"status": "pass"},
                        "source_integrity": {"status": "pass"},
                    },
                }
            ),
            encoding="utf-8",
        )
        summary.write_text(
            json.dumps(
                {
                    "report": "evaluation/reports/acceptance.json",
                    "sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
                }
            ),
            encoding="utf-8",
        )

    save("a" * 40)
    first = status_report.build(tmp_path)
    assert first["master_release"]["tiers"]["local_demo"]["status"] == "verified"
    assert (
        first["subsystem_capabilities"]["schema_version"]
        == "subsystem_capability_manifest_v1"
    )
    save("b" * 40)
    assert (
        status_report.build(tmp_path)["master_release"]["tiers"]["local_demo"]["status"]
        == "not_established"
    )
    save("a" * 40)
    report.write_text("{}", encoding="utf-8")
    assert (
        status_report.build(tmp_path)["master_release"]["tiers"]["local_demo"]["status"]
        == "not_established"
    )
