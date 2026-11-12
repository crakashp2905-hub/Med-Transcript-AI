"""Single-command, read-only local readiness report; never runs inference."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from services.engineering_status import evidence_record, validate
from services.offline_preflight import inspect
from services.master_release import assess
from services.capability_manifest import build as capability_manifest


def build(root="."):
    root = Path(root).resolve()
    ledger = json.loads(
        (root / "evaluation/reports/engineering-task-status.json").read_text(
            encoding="utf-8"
        )
    )
    try:
        counts = validate(ledger, root)
    except ValueError as exc:
        counts = {
            "total": ledger["total"],
            "verified": None,
            "status": "evidence_requires_revalidation",
            "error_code": str(exc),
            "real_patient_release_authorized": False,
        }
    acceptance_path = root / "data/offline-acceptance-summary.json"
    acceptance = (
        json.loads(acceptance_path.read_text(encoding="utf-8"))
        if acceptance_path.is_file()
        else None
    )
    checks = acceptance.get("checks", {}) if isinstance(acceptance, dict) else {}
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unavailable"
    current_demo_pass = False
    if isinstance(acceptance, dict):
        relative = acceptance.get("report")
        if isinstance(relative, str) and relative:
            candidate = (root / relative).resolve()
            if candidate.is_relative_to(root) and candidate.is_file():
                try:
                    report = json.loads(candidate.read_text(encoding="utf-8"))
                    current_demo_pass = (
                        hashlib.sha256(candidate.read_bytes()).hexdigest()
                        == acceptance.get("sha256")
                        and report.get("source_commit") == commit
                        and report.get("checks", {})
                        .get("synthetic_walkthrough", {})
                        .get("status")
                        == "pass"
                        and report.get("checks", {})
                        .get("source_integrity", {})
                        .get("status")
                        == "pass"
                    )
                except (OSError, ValueError):
                    pass
    source_files = (
        "pyproject.toml",
        "constraints-ci.txt",
        "services/engineering_status.py",
        "services/offline_preflight.py",
        "services/capability_manifest.py",
        "services/asr/provenance.py",
        "services/release_policy.py",
    )
    return {
        "schema_version": "local_status_v1",
        "git_commit": commit,
        "offline_mode": os.getenv("MED_TRANSCRIPT_OFFLINE") == "1",
        "test_status": {
            "latest_acceptance": {
                k: v.get("status") if isinstance(v, dict) else v
                for k, v in checks.items()
            },
            "source": "saved_acceptance_only",
            "inference_executed": False,
        },
        "model_availability": inspect(root)["models"],
        "subsystem_capabilities": capability_manifest(),
        "source_hashes": [
            evidence_record(name, root)
            for name in source_files
            if (root / name).is_file()
        ],
        "engineering": counts,
        "master_release": assess(current_demo_pass=current_demo_pass),
        "clinical_release": "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED",
        "real_patient_release_authorized": False,
        "limitations": "Read-only diagnostics; a saved test receipt is not a fresh test run and model presence is not model eligibility.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    print(json.dumps(build(args.root), indent=2))
