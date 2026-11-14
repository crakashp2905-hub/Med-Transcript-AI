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


def readiness_checks(
    *,
    offline_mode,
    acceptance_present,
    current_demo_pass,
    engineering_evidence_valid,
    production_model_selected=False,
):
    checks = {
        "offline_mode": {
            "status": "PASS" if offline_mode else "UNKNOWN",
            "reason": "Offline environment flag is enabled."
            if offline_mode
            else "Offline mode was not confirmed in this process.",
        },
        "latest_acceptance": {
            "status": "PASS"
            if current_demo_pass
            else "BLOCKED"
            if acceptance_present
            else "UNKNOWN",
            "reason": "Current-source offline acceptance receipt is valid."
            if current_demo_pass
            else "Saved receipt is stale, invalid, incomplete, or failed."
            if acceptance_present
            else "No saved offline acceptance receipt is available.",
        },
        "engineering_evidence": {
            "status": "PASS" if engineering_evidence_valid else "BLOCKED",
            "reason": "Engineering evidence ledger passed local hash validation."
            if engineering_evidence_valid
            else "Engineering evidence is stale or failed local hash validation.",
        },
        "asr_model_admission": {
            "status": "BLOCKED" if not production_model_selected else "UNKNOWN",
            "reason": "No qualifying model is admitted; the 5% normalized-WER gate remains unmet."
            if not production_model_selected
            else "Model selection exists but this read-only CLI does not re-evaluate benchmark eligibility.",
        },
        "clinical_validation": {
            "status": "BLOCKED",
            "reason": "Independent clinical validation and qualified review are not available.",
        },
        "identity_provider_activation": {
            "status": "UNKNOWN",
            "reason": "Institution identity-provider registration and credentials are not confirmed by this local check.",
        },
        "physical_audio_hardware": {
            "status": "UNKNOWN",
            "reason": "No named microphone/interface and physical channel test are recorded.",
        },
        "ehr_receiver_validation": {
            "status": "UNKNOWN",
            "reason": "No receiver-specific profile or authorized EHR sandbox validation is recorded.",
        },
    }
    status = [check["status"] for check in checks.values()]
    checks["overall"] = {
        "status": "BLOCKED"
        if "BLOCKED" in status
        else "UNKNOWN"
        if "UNKNOWN" in status
        else "PASS",
        "reason": "One or more release prerequisites are blocked or unknown.",
    }
    return checks


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
    engineering_evidence_valid = counts.get("verified") is not None and not counts.get(
        "error_code"
    )
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
    model_registry_path = root / "evaluation/model-registry.json"
    production_model_selected = False
    if model_registry_path.is_file():
        try:
            production_model_selected = bool(
                json.loads(model_registry_path.read_text(encoding="utf-8")).get(
                    "production_model_selected"
                )
            )
        except (OSError, ValueError):
            production_model_selected = False
    offline_mode = os.getenv("MED_TRANSCRIPT_OFFLINE") == "1"
    required_checks = readiness_checks(
        offline_mode=offline_mode,
        acceptance_present=isinstance(acceptance, dict),
        current_demo_pass=current_demo_pass,
        engineering_evidence_valid=engineering_evidence_valid,
        production_model_selected=production_model_selected,
    )
    missing_checks = [
        {"check": name, **value}
        for name, value in required_checks.items()
        if value["status"] in {"BLOCKED", "UNKNOWN"}
    ]
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
        "offline_mode": offline_mode,
        "readiness_checks": required_checks,
        "missing_checks": missing_checks,
        "test_status": {
            "latest_acceptance": {
                k: v.get("status") if isinstance(v, dict) else v
                for k, v in checks.items()
            },
            "source": "saved_acceptance_only",
            "inference_executed": False,
            "receipt_status": required_checks["latest_acceptance"]["status"],
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
