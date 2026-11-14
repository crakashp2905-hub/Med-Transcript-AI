"""Local diagnostics; no external calls or persistent writes except an optional report."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from services.engineering_status import sha256


def git_state(root):
    def run(*args):
        try:
            result = subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True,
                timeout=5, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result.stdout.strip() if result.returncode == 0 else None

    commit = run("rev-parse", "HEAD")
    dirty = run("status", "--porcelain", "--untracked-files=no")
    return {
        "head": commit,
        "tracked_worktree_clean": dirty == "" if dirty is not None else None,
        "dirty_tracked_paths": [line[3:] for line in dirty.splitlines()] if dirty else [],
    }


def permission_probe(path):
    path = Path(path)
    exists = path.is_dir()
    readable = exists and os.access(path, os.R_OK | os.X_OK)
    writable = False
    if exists and os.access(path, os.W_OK | os.X_OK):
        try:
            with tempfile.NamedTemporaryFile(prefix=".offline-diagnostic-", dir=path):
                pass
            writable = True
        except OSError:
            writable = False
    return {"path": path.as_posix(), "exists": exists, "readable": readable, "writable_probe": writable}


def configured_model_directories(root):
    suite_path = root / "evaluation/detailed-suite-v7.json"
    if not suite_path.is_file():
        return {"status": "blocked_missing_local_artifact", "present": [], "missing": []}
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    candidates = {}
    unconfigured = set()
    for job in suite.get("jobs", []):
        model_dir = job.get("model_dir")
        if isinstance(model_dir, str) and model_dir:
            candidates.setdefault(model_dir, set()).add(job.get("candidate_id", "unknown"))
        else:
            unconfigured.add(job.get("candidate_id", "unknown"))
    present, missing = [], []
    for relative, names in sorted(candidates.items()):
        item = {"path": relative, "candidate_ids": sorted(names)}
        (present if (root / relative).is_dir() else missing).append(item)
    return {
        "status": "measured",
        "present": present,
        "missing": missing,
        "unconfigured_candidate_ids": sorted(unconfigured),
    }


def latest_acceptance(root):
    summary_path = root / "data/offline-acceptance-summary.json"
    if not summary_path.is_file():
        return {"status": "not_available", "blocked_checks": [], "failed_tests": [], "skipped_tests": []}
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        report_path = (root / summary["report"]).resolve()
        if not report_path.is_relative_to(root) or not report_path.is_file():
            raise ValueError("acceptance_report_missing_or_outside_repository")
        if summary.get("sha256") != sha256(report_path):
            raise ValueError("acceptance_report_hash_mismatch")
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return {"status": "invalid_or_unavailable", "blocked_checks": [], "failed_tests": [], "skipped_tests": []}
    checks = report.get("checks", {})
    if isinstance(checks, list):
        checks = {item.get("name", "unknown"): item for item in checks if isinstance(item, dict)}
    blocked = sorted(name for name, item in checks.items() if isinstance(item, dict) and item.get("status") != "pass")
    backend = checks.get("backend_tests", {})
    detail = backend.get("detail", {}) if isinstance(backend, dict) else {}
    test_result = detail.get("test_result", {}) if isinstance(detail, dict) else {}
    return {
        "status": "available",
        "report": report_path.relative_to(root).as_posix(),
        "report_sha256": sha256(report_path),
        "blocked_checks": blocked,
        "failed_tests": test_result.get("failed_test_ids", []),
        "skipped_tests": test_result.get("skipped_tests", []),
    }


def inspect(root="."):
    root = Path(root).resolve()
    from services.offline_preflight import inspect as inspect_preflight
    from services.offline_acceptance import source_inventory
    from services.source_change_detector import compare_acceptance, toolchain_inventory

    capabilities = inspect_preflight(root=root)
    sources = source_inventory(root)
    source_digest = hashlib.sha256(
        json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    acceptance = latest_acceptance(root)
    freshness = {"status": "not_available", "reasons": []}
    if acceptance.get("status") == "available":
        acceptance_document = json.loads((root / acceptance["report"]).read_text(encoding="utf-8"))
        freshness = compare_acceptance(
            acceptance_document, source_files=sources, toolchain=toolchain_inventory()
        )
    disk = shutil.disk_usage(root)
    total_model_dirs = configured_model_directories(root)
    permissions = [permission_probe(root / rel) for rel in ("data", "evaluation/reports")]
    return {
        "schema_version": "offline_diagnostics_v1",
        "source": {**git_state(root), "source_file_count": len(sources), "source_sha256": source_digest, "acceptance_freshness": freshness},
        "models": {"candidate_directories": total_model_dirs, "preflight_inventory": capabilities.get("models", [])},
        "disk": {"total_bytes": disk.total, "free_bytes": disk.free, "used_percent": round(100 * disk.used / disk.total, 2) if disk.total else None},
        "permissions": permissions,
        "tests": acceptance,
        "toolchain": capabilities.get("runtime_versions", {}),
        "external_calls_attempted": 0,
        "installations_attempted": 0,
        "clinical_release_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root; no persistent files are changed except --out.")
    parser.add_argument("--out", help="Optional new JSON report path; existing files are never overwritten.")
    args = parser.parse_args()
    report = inspect(args.root)
    encoded = json.dumps(report, indent=2) + "\n"
    if args.out:
        output = Path(args.out)
        if not output.is_absolute():
            output = Path(args.root) / output
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
