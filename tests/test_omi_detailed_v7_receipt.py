import hashlib
import json
from pathlib import Path


def test_omi_detailed_v7_receipt_binds_locked_run_and_keeps_gate_failure():
    receipt_path = Path("evaluation/reports/master-task-mta-04-18-fb21680.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    runtime = receipt["runtime"]
    run_path = Path("evaluation/runs/meddistract-detailed-v7/omi-med-stt-v1.fixed.json")
    lock_path = Path(
        "evaluation/experiments/detailed-suite-v7-original-lock-2026-11-13.json"
    )
    run = json.loads(run_path.read_text(encoding="utf-8"))

    assert receipt["task_id"] == "MTA-04-18"
    assert receipt["source_commit"] == "fb21680b6cf7ca5d6afaa0299f497e8637230bf5"
    assert (
        hashlib.sha256(run_path.read_bytes()).hexdigest()
        == receipt["source_sha256"][str(run_path).replace("\\", "/")]
    )
    assert (
        hashlib.sha256(lock_path.read_bytes()).hexdigest()
        == runtime["suite_snapshot_sha256"]
    )
    assert runtime["manifest_sha256"] == run["manifest_sha256"]
    assert run["complete"] is True and len(run["cases"]) == 16
    assert receipt["checks"]["five_percent_quality_gate"]["status"] == "fail"
    assert all(
        runtime["conditions"][condition]["gate"] == "fail"
        for condition in ("clean", "distracted")
    )
    assert all(
        runtime["conditions"][condition]["failed_samples"] == 1
        for condition in ("clean", "distracted")
    )
    assert runtime["paid_calls"] == runtime["external_assets_fetched"] == 0
    assert (
        receipt["runtime_sha256"]
        == hashlib.sha256(
            json.dumps(runtime, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
