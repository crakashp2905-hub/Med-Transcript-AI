"""Run deterministic, dependency-ordered repository checks without installing tools."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTEST_FAILURE = re.compile(r"^FAILED ([A-Za-z0-9_./-]+)::([A-Za-z_][A-Za-z0-9_]*)")
PYTEST_ERROR = re.compile(r"^ERROR ([A-Za-z0-9_./-]+)::([A-Za-z_][A-Za-z0-9_]*)")
PYTEST_SUMMARY = re.compile(
    r"\b\d+ (?:passed|failed|skipped|warnings?|errors?|deselected|xfailed|xpassed)\b"
)


def safe_pytest_diagnostics(output):
    """Return aggregate test counts and parameter-free test names only."""
    lines = (output or "").splitlines()
    summary_line = next(
        (line for line in reversed(lines) if PYTEST_SUMMARY.search(line)), ""
    )
    summary = ", ".join(PYTEST_SUMMARY.findall(summary_line)) or "summary unavailable"
    failures = []
    errors = []
    for line in lines:
        match = PYTEST_FAILURE.match(line)
        if match:
            failures.append(f"{match.group(1)}::{match.group(2)}")
        match = PYTEST_ERROR.match(line)
        if match:
            errors.append(f"{match.group(1)}::{match.group(2)}")
    return {
        "summary": summary,
        "failed_tests": sorted(set(failures))[:50],
        "error_tests": sorted(set(errors))[:50],
    }


def verification_steps(*, python_only=False):
    steps = [
        (
            "python_format",
            [sys.executable, "-m", "ruff", "format", "--check", "services", "tests"],
            ROOT,
        ),
        (
            "python_lint",
            [sys.executable, "-m", "ruff", "check", "services", "tests"],
            ROOT,
        ),
        (
            "python_types",
            [sys.executable, "-m", "mypy", "services", "--ignore-missing-imports"],
            ROOT,
        ),
        ("python_tests", [sys.executable, "-m", "pytest", "-q"], ROOT),
    ]
    if not python_only:
        steps.append(
            (
                "frontend_build",
                ["npm", "run", "build"],
                ROOT / "apps/clinician-web",
            )
        )
    return steps


def run_verification(*, python_only=False, runner=subprocess.run):
    results = []
    for name, command, cwd in verification_steps(python_only=python_only):
        print(json.dumps({"check": name, "status": "running"}), flush=True)
        try:
            result = runner(
                command, cwd=cwd, check=False, capture_output=True, text=True
            )
            returncode = result.returncode
        except OSError as exc:
            returncode = 127
            print(f"{name}: executable unavailable ({type(exc).__name__})")
        result_status = "pass" if returncode == 0 else "fail"
        entry = {"check": name, "status": result_status, "exit_code": returncode}
        if name == "python_tests":
            entry.update(safe_pytest_diagnostics(getattr(result, "stdout", "")))
        results.append(entry)
        print(json.dumps(results[-1]), flush=True)
        if returncode:
            break
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python-only",
        action="store_true",
        help="Run Python format, lint, type and test checks; omit the frontend build.",
    )
    args = parser.parse_args()
    results = run_verification(python_only=args.python_only)
    raise SystemExit(
        0 if results and all(r["status"] == "pass" for r in results) else 1
    )


if __name__ == "__main__":
    main()
