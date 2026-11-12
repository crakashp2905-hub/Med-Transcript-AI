import copy
import hashlib
import json

import pytest

from services.master_ledger import LEDGER, ROOT, audit


def test_supplied_ledger_has_unique_369_tasks_without_completion_claims():
    result = audit()
    assert result["total"] == 369
    assert result["statuses"]["not_started"] == 354
    assert result["statuses"]["blocked_missing_asset"] == 3
    assert result["statuses"]["implemented"] == 12
    assert result["verified_at_current_commit"] == 0
    assert result["clinical_release_authorized"] is False
    document = json.loads(LEDGER.read_text(encoding="utf-8"))
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
    blocked_task = next(item for item in document["tasks"] if item["id"] == "MTA-01-03")
    assert blocked_task["status"] == "blocked_missing_asset"
    assert blocked_task["source_commit"] == "c15c2b896e69e66c110d59b2f805b59ce9c165e1"
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


def test_verified_task_requires_matching_commit_and_hashed_passing_result(tmp_path):
    document = json.loads(LEDGER.read_text(encoding="utf-8"))
    task = document["tasks"][0]
    task.update(
        status="verified",
        source_commit="a" * 40,
        evidence=["evaluation/master-task-ledger.json"],
    )
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="missing_test_receipt"):
        audit(path, head="a" * 40)

    source = ROOT / "evaluation/reports/offline-acceptance-v21.json"
    report = json.loads(source.read_text(encoding="utf-8"))
    task["source_commit"] = report["source_commit"]
    task["test_results"] = [
        {
            "report": source.relative_to(ROOT).as_posix(),
            "report_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "check": "backend_tests",
            "status": "pass",
        }
    ]
    path.write_text(json.dumps(document), encoding="utf-8")
    assert audit(path, head=task["source_commit"])["verified_at_current_commit"] == 1
    broken = copy.deepcopy(document)
    broken["tasks"][0]["test_results"][0]["report_sha256"] = "0" * 64
    path.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(ValueError, match="report_hash_mismatch"):
        audit(path, head=task["source_commit"])
