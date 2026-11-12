import hashlib
import json

import pytest

from services import master_ledger
from services.master_ledger import LEDGER, audit


def test_supplied_ledger_has_unique_369_tasks_and_audited_statuses():
    result = audit()
    assert result["total"] == 369
    assert sum(result["statuses"].values()) == 369
    assert result["statuses"]["blocked_missing_asset"] == 3
    assert result["statuses"]["verified"] == 3
    assert result["clinical_release_authorized"] is False
    document = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert result["verified_at_current_commit"] == sum(
        task["status"] == "verified"
        and task["source_commit"] == result["source_commit"]
        for task in document["tasks"]
    )
    baseline_task = next(
        item for item in document["tasks"] if item["id"] == "MTA-00-01"
    )
    assert baseline_task["status"] == "implemented"
    assert baseline_task["source_commit"] == "b93937756427d1ae86adf847c680ed52c187b9ed"
    scope_task = next(item for item in document["tasks"] if item["id"] == "MTA-00-02")
    assert scope_task["status"] == "implemented"
    assert scope_task["source_commit"] == "eab55f948573a5dcb5ad07e884bcbefc28026206"
    artifact_task = next(
        item for item in document["tasks"] if item["id"] == "MTA-00-03"
    )
    assert artifact_task["status"] == "implemented"
    assert artifact_task["source_commit"] == "97572f7cf47523df64d7e1470aa17865809d8ae6"
    offline_task = next(item for item in document["tasks"] if item["id"] == "MTA-00-04")
    assert offline_task["status"] == "implemented"
    assert offline_task["source_commit"] == "eab55f948573a5dcb5ad07e884bcbefc28026206"
    tier_task = next(item for item in document["tasks"] if item["id"] == "MTA-00-05")
    assert tier_task["status"] == "implemented"
    assert tier_task["source_commit"] == "bb809e7a10a3b47cc7b4b9a5ed527690fbb54bcf"
    matrix_task = next(item for item in document["tasks"] if item["id"] == "MTA-00-06")
    assert matrix_task["status"] == "implemented"
    assert matrix_task["source_commit"] == "4bd27b2555d8e7f51e82f06b220a97de5aacc9db"
    risk_task = next(item for item in document["tasks"] if item["id"] == "MTA-00-07")
    assert risk_task["status"] == "implemented"
    assert risk_task["source_commit"] == "c158cca2a6c382ed538de4dee256187d8e2f52ec"
    wer_task = next(item for item in document["tasks"] if item["id"] == "MTA-00-08")
    assert wer_task["status"] == "implemented"
    assert wer_task["source_commit"] == "cdb7b0b43eed389cc52550b01f512c30f47c67b0"
    gold_task = next(item for item in document["tasks"] if item["id"] == "MTA-00-09")
    assert gold_task["status"] == "implemented"
    assert gold_task["source_commit"] == "8b547e25cc929c2333757a49214f43128dd04368"
    task = next(item for item in document["tasks"] if item["id"] == "MTA-04-06")
    assert task["status"] == "implemented"
    assert task["source_commit"] == "7c6102499980a0a8095ffc3a403809e3da23f69e"
    format_task = next(item for item in document["tasks"] if item["id"] == "MTA-01-06")
    assert format_task["status"] == "implemented"
    assert format_task["source_commit"] == "796a9d9b07338b3bb7d1735df43a7cc916aa2231"
    frontend_task = next(
        item for item in document["tasks"] if item["id"] == "MTA-01-04"
    )
    assert frontend_task["status"] == "blocked_missing_asset"
    assert frontend_task["source_commit"] == "aef2a7b25291c1900cf31e8952ab3822cec4091a"
    ci_task = next(item for item in document["tasks"] if item["id"] == "MTA-01-03")
    assert ci_task["status"] == "verified"
    assert ci_task["source_commit"] == "ab04b795d8c597e792d591bb3b90c804473d208f"
    exact_head_task = next(
        item for item in document["tasks"] if item["id"] == "MTA-01-05"
    )
    assert exact_head_task["status"] == "verified"
    assert exact_head_task["source_commit"] == ci_task["source_commit"]
    contract_task = next(
        item for item in document["tasks"] if item["id"] == "MTA-01-14"
    )
    assert contract_task["status"] == "verified"
    assert contract_task["source_commit"] == "94d5c55fff4dea045c640b098d39fbb8a4b79d19"
    documentation_task = next(
        item for item in document["tasks"] if item["id"] == "MTA-01-08"
    )
    assert documentation_task["status"] == "implemented"
    assert (
        documentation_task["source_commit"]
        == "03b103d4b010df262891a0c972412f163649656f"
    )
    provenance_task = next(
        item for item in document["tasks"] if item["id"] == "MTA-01-07"
    )
    assert provenance_task["status"] == "implemented"
    assert (
        provenance_task["source_commit"] == "d06fdca0f68168edf3019a857c8a4b55c78db375"
    )
    runtime_task = next(item for item in document["tasks"] if item["id"] == "MTA-01-09")
    assert runtime_task["status"] == "blocked_missing_asset"
    assert runtime_task["source_commit"] == "9093e5ffd863697618eeb2eef80171b430105684"
    repro_task = next(item for item in document["tasks"] if item["id"] == "MTA-01-10")
    assert repro_task["status"] == "implemented"
    assert repro_task["source_commit"] == "45b8f07bea3bac574b18a6596acd128eea4a8ac9"
    skip_task = next(item for item in document["tasks"] if item["id"] == "MTA-01-11")
    assert skip_task["status"] == "implemented"
    assert skip_task["source_commit"] == "c15c2b896e69e66c110d59b2f805b59ce9c165e1"
    dependency_audit = next(
        item for item in document["tasks"] if item["id"] == "MTA-01-18"
    )
    assert dependency_audit["status"] == "blocked_missing_asset"
    assert "No local offline vulnerability scanner" in dependency_audit["blocker"]
    release_summary = next(
        item for item in document["tasks"] if item["id"] == "MTA-01-20"
    )
    assert release_summary["status"] == "implemented"
    assert (
        release_summary["source_commit"] == "906f0fc688fb0b0f5693fe913087bc459e82f4b8"
    )
    sequence_diagram = next(
        item for item in document["tasks"] if item["id"] == "MTA-02-01"
    )
    assert sequence_diagram["status"] == "implemented"
    assert (
        sequence_diagram["source_commit"] == "5001f9c21ad7744dd139c212386848cf9c329106"
    )
    service_catalog = next(
        item for item in document["tasks"] if item["id"] == "MTA-02-02"
    )
    assert service_catalog["status"] == "implemented"
    assert (
        service_catalog["source_commit"] == "2140b352f4c80986fdbc3c8c1413f96d5c1fcbde"
    )
    typed_schemas = next(
        item for item in document["tasks"] if item["id"] == "MTA-02-03"
    )
    assert typed_schemas["status"] == "implemented"
    assert typed_schemas["source_commit"] == "0520ea2899b7c92bcbe9baa6633b36979170b503"


def test_verified_task_requires_exact_commit_test_and_runtime_hashes(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(master_ledger, "ROOT", tmp_path)
    (tmp_path / "evaluation/reports").mkdir(parents=True)
    (tmp_path / "evaluation/master-task-ledger.json").write_text("{}")
    task = {
        "id": "MTA-TEST",
        "status": "verified",
        "source_commit": "a" * 40,
        "evidence": ["evaluation/master-task-ledger.json"],
        "test_results": [],
    }
    document = {"total": 1, "tasks": [task]}
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="missing_test_receipt"):
        audit(path, head="a" * 40)

    runtime = {"python": "3.x", "platform": "test"}
    runtime_hash = hashlib.sha256(
        json.dumps(runtime, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    report = {
        "source_commit": "a" * 40,
        "runtime": runtime,
        "runtime_sha256": runtime_hash,
        "checks": {"unit_tests": {"status": "pass"}},
    }
    report_path = tmp_path / "evaluation/reports/run.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    task["test_results"] = [
        {
            "report": "evaluation/reports/run.json",
            "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
            "check": "unit_tests",
            "status": "pass",
        }
    ]
    path.write_text(json.dumps(document), encoding="utf-8")
    assert audit(path, head=task["source_commit"])["verified_at_current_commit"] == 1

    report["runtime_sha256"] = "0" * 64
    report_path.write_text(json.dumps(report), encoding="utf-8")
    task["test_results"][0]["report_sha256"] = hashlib.sha256(
        report_path.read_bytes()
    ).hexdigest()
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="runtime_hash_mismatch"):
        audit(path, head=task["source_commit"])
