"""Capture an immutable, local-only starting receipt for the 369-task ledger."""

import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "evaluation/master-task-ledger.json"
REPORTS = ROOT / "evaluation/reports"


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def command(*argv):
    executable = shutil.which(argv[0])
    if not executable:
        return None
    try:
        result = subprocess.run((executable, *argv[1:]), cwd=ROOT, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def main():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    if ledger["total"] != len(ledger["tasks"]) or len({task["id"] for task in ledger["tasks"]}) != ledger["total"]:
        raise ValueError("invalid_master_task_ledger")
    head = command("git", "rev-parse", "HEAD")
    if head != ledger["baseline_commit"]:
        raise ValueError("baseline_commit_mismatch")
    output = REPORTS / f"master-baseline-{head[:7]}.json"
    if output.exists():
        raise FileExistsError("baseline_receipt_is_immutable")
    model_root = ROOT / "data/models"
    models = {
        path.relative_to(ROOT).as_posix(): {"bytes": path.stat().st_size, "sha256": digest(path)}
        for path in sorted(model_root.rglob("*")) if path.is_file()
    }
    development_manifests = {
        path.relative_to(ROOT).as_posix(): digest(path)
        for path in sorted((ROOT / "evaluation/datasets").glob("*/manifest.json"))
        if "acceptance" not in path.as_posix().lower()
    }
    frozen_reports = {
        path.relative_to(ROOT).as_posix(): digest(path)
        for path in (
            ROOT / "evaluation/reports/offline-acceptance-v20.json",
            ROOT / "evaluation/reports/offline-acceptance-v21.json",
            ROOT / "evaluation/reports/scope-separated-baselines-v1.json",
        ) if path.is_file()
    }
    packages = {}
    for name in ("fastapi", "pydantic", "pytest", "ruff", "mypy", "faster-whisper", "numpy"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    receipt = {
        "schema_version": "master_baseline_v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": head,
        "initial_git_status_at_audit": "clean; main matched origin/main before ledger copy",
        "capture_git_status": command("git", "status", "--short"),
        "ledger_path": LEDGER.relative_to(ROOT).as_posix(),
        "ledger_sha256": digest(LEDGER),
        "ledger_task_count": ledger["total"],
        "python": sys.version,
        "platform": platform.platform(),
        "node": command("node", "--version"),
        "npm": command("npm", "--version"),
        "packages": packages,
        "development_dataset_manifest_sha256": development_manifests,
        "local_model_files": models,
        "frozen_report_sha256": frozen_reports,
        "last_ci": {
            "run_id": 43099092013,
            "head_sha": head,
            "conclusion": "failure",
            "failed_job": "test (dev,security): Ruff format check",
            "cancelled_job": "test (dev,asr,security): dependency installation cancelled",
            "url": "https://github.com/crakashp2905-hub/Med-Transcript-AI/actions/runs/43099092013",
        },
        "reserved_acceptance_cohort_read": False,
        "real_patient_release_authorized": False,
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": output.relative_to(ROOT).as_posix(), "models_hashed": len(models),
                      "development_manifests_hashed": len(development_manifests), "baseline_commit": head}))


if __name__ == "__main__":
    main()
