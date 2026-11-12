"""Run deterministic, dependency-ordered repository checks without installing tools."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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
        results.append(
            {"check": name, "status": result_status, "exit_code": returncode}
        )
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
