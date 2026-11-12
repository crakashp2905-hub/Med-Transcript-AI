"""Validate the in-house task ledger without promoting unsupported claims."""

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "evaluation/master-task-ledger.json"
STATUSES = {
    "not_started",
    "implemented",
    "verified",
    "failed",
    "blocked_missing_asset",
    "blocked_external_evidence",
}
COMMIT = re.compile(r"[0-9a-f]{40}\Z")


def _local_file(relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("evidence_path_must_be_relative")
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError("evidence_path_missing_or_external")
    return path


def _receipt(task, result, *, require_runtime=False):
    if not isinstance(result, dict) or result.get("status") not in {
        "pass",
        "fail",
        "blocked",
    }:
        raise ValueError(f"{task['id']}: invalid_test_result")
    report_path = _local_file(result.get("report"))
    actual = hashlib.sha256(report_path.read_bytes()).hexdigest()
    if actual != result.get("report_sha256"):
        raise ValueError(f"{task['id']}: report_hash_mismatch")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("source_commit") != task["source_commit"]:
        raise ValueError(f"{task['id']}: report_commit_mismatch")
    if require_runtime:
        runtime = report.get("runtime")
        runtime_hash = report.get("runtime_sha256")
        if not isinstance(runtime, dict) or not runtime:
            raise ValueError(f"{task['id']}: missing_runtime_receipt")
        expected_runtime_hash = hashlib.sha256(
            json.dumps(runtime, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        # Accept only the canonical JSON digest so receipt serialization is stable.
        if runtime_hash != expected_runtime_hash:
            raise ValueError(f"{task['id']}: runtime_hash_mismatch")
        if not result.get("check"):
            raise ValueError(f"{task['id']}: verified_test_name_required")
    check = result.get("check")
    if (
        check is not None
        and report.get("checks", {}).get(check, {}).get("status") != result["status"]
    ):
        raise ValueError(f"{task['id']}: check_result_mismatch")


def audit(path=LEDGER, head=None):
    ledger = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = ledger.get("tasks")
    if not isinstance(tasks, list) or ledger.get("total") != len(tasks):
        raise ValueError("ledger_count_mismatch")
    ids = [task.get("id") for task in tasks]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate_task_id")
    if head is None:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    counts = Counter()
    current_verified = 0
    for task in tasks:
        status = task.get("status")
        if status not in STATUSES:
            raise ValueError(f"{task['id']}: unknown_status")
        counts[status] += 1
        if status == "not_started":
            continue
        commit = task.get("source_commit")
        if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
            raise ValueError(f"{task['id']}: missing_exact_commit")
        evidence = task.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"{task['id']}: missing_evidence")
        for relative in evidence:
            _local_file(relative)
        results = task.get("test_results")
        if not isinstance(results, list) or not results:
            raise ValueError(f"{task['id']}: missing_test_receipt")
        for result in results:
            _receipt(task, result, require_runtime=status == "verified")
        if status == "verified":
            if any(result["status"] != "pass" for result in results):
                raise ValueError(f"{task['id']}: failed_result_claimed_verified")
            current_verified += commit == head
    return {
        "schema_version": "master_ledger_audit_v1",
        "ledger_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "source_commit": head,
        "total": len(tasks),
        "statuses": {status: counts[status] for status in sorted(STATUSES)},
        "verified_at_current_commit": current_verified,
        "clinical_release_authorized": False,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
