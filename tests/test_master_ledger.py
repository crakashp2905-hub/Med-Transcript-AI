import copy
import hashlib
import json

import pytest

from services.master_ledger import LEDGER, ROOT, audit


def test_supplied_ledger_has_unique_369_tasks_without_completion_claims():
    result = audit()
    assert result["total"] == 369
    assert result["statuses"]["not_started"] == 366
    assert result["statuses"]["implemented"] == 3
    assert result["verified_at_current_commit"] == 0
    assert result["clinical_release_authorized"] is False
    document = json.loads(LEDGER.read_text(encoding="utf-8"))
    task = next(item for item in document["tasks"] if item["id"] == "MTA-04-06")
    assert task["status"] == "implemented"
    assert task["source_commit"] == "7c6102499980a0a8095ffc3a403809e3da23f69e"
    format_task = next(item for item in document["tasks"] if item["id"] == "MTA-01-06")
    assert format_task["status"] == "implemented"
    assert format_task["source_commit"] == "796a9d9b07338b3bb7d1735df43a7cc916aa2231"
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
