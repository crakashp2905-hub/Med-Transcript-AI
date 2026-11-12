"""Invalidate saved acceptance when its source or execution toolchain changes."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def canonical_sha256(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def toolchain_inventory():
    packages = sorted(
        (dist.metadata.get("Name", "").lower(), dist.version)
        for dist in importlib.metadata.distributions()
        if dist.metadata.get("Name")
    )

    def executable_version(name, flag):
        executable = shutil.which(name)
        if not executable:
            return None
        try:
            result = subprocess.run(
                [executable, flag], capture_output=True, text=True, timeout=5
            )
        except (OSError, subprocess.TimeoutExpired):
            return "unavailable"
        if result.returncode:
            return "unavailable"
        return (result.stdout or result.stderr).strip().splitlines()[0][:200]

    return {
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "python_executable": Path(sys.executable).name,
        "packages": packages,
        "node_version": executable_version("node", "--version"),
        "npm_version": executable_version("npm", "--version"),
    }


def compare_acceptance(acceptance, *, source_files, toolchain):
    reasons = []
    expected_source = acceptance.get("source_sha256")
    if not isinstance(expected_source, dict) or expected_source != source_files:
        reasons.append("source_hash_mismatch")
    expected_toolchain = acceptance.get("toolchain")
    expected_digest = acceptance.get("toolchain_sha256")
    if (
        not isinstance(expected_toolchain, dict)
        or not expected_toolchain
        or expected_digest != canonical_sha256(expected_toolchain)
    ):
        reasons.append("toolchain_fingerprint_missing_or_invalid")
    elif expected_toolchain != toolchain:
        reasons.append("toolchain_changed")
    return {
        "schema_version": "acceptance_freshness_v1",
        "status": "invalidated" if reasons else "valid",
        "invalidated": bool(reasons),
        "reasons": reasons,
        "source_files_compared": len(source_files),
        "toolchain_sha256": canonical_sha256(toolchain),
    }


def inspect_report(report_path):
    from services.offline_acceptance import source_inventory

    path = Path(report_path)
    acceptance = json.loads(path.read_text(encoding="utf-8"))
    return compare_acceptance(
        acceptance,
        source_files=source_inventory(),
        toolchain=toolchain_inventory(),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("acceptance_report")
    args = parser.parse_args()
    result = inspect_report(args.acceptance_report)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["invalidated"] else 0)


if __name__ == "__main__":
    main()
