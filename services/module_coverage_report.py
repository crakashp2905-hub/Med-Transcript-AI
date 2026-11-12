"""Create a small branch-coverage report for critical engineering modules."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CRITICAL_MODULES = (
    "services/critical_mutation_campaign.py",
    "services/master_ledger.py",
)
TESTS = (
    "tests/test_critical_mutation_campaign.py",
    "tests/test_master_ledger.py",
)


def summarize_coverage(document, *, source_commit):
    files = {
        path.replace("\\", "/"): value
        for path, value in document.get("files", {}).items()
    }
    modules = {}
    for path in CRITICAL_MODULES:
        metrics = files.get(path)
        if not isinstance(metrics, dict):
            raise ValueError(f"coverage_module_missing:{path}")
        summary = metrics.get("summary", {})
        branches = summary.get("num_branches", 0)
        covered = summary.get("covered_branches", 0)
        modules[path] = {
            "lines_found": summary.get("num_statements", 0),
            "lines_covered": summary.get("covered_lines", 0),
            "line_percent": summary.get("percent_covered", 0.0),
            "branches_found": branches,
            "branches_covered": covered,
            "branch_percent": round(covered * 100 / branches, 2) if branches else None,
        }
    return {
        "schema_version": "critical_module_coverage_v1",
        "source_commit": source_commit,
        "coverage_tool": "coverage.py",
        "branch_measurement": True,
        "tests": list(TESTS),
        "modules": modules,
        "interpretation": "Coverage is a test-execution diagnostic; it does not establish behavioral correctness or clinical safety.",
    }


def run(source_commit, output):
    with tempfile.TemporaryDirectory(prefix="med-transcript-coverage-") as temp:
        data_file = Path(temp) / ".coverage"
        raw_json = Path(temp) / "coverage.json"
        env = os.environ.copy()
        env["COVERAGE_FILE"] = str(data_file)
        command = [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--branch",
            "--source=services.critical_mutation_campaign,services.master_ledger",
            "-m",
            "pytest",
            "-q",
            *TESTS,
        ]
        try:
            test_result = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                check=False,
                timeout=180,
                capture_output=True,
                text=True,
            )
        except subprocess.TimeoutExpired:
            print("Critical module coverage test run timed out after 180 seconds.")
            return 124
        if test_result.returncode:
            print("Critical module coverage tests failed; assertion output suppressed.")
            return test_result.returncode
        terminal = next(
            (
                line.strip()
                for line in reversed((test_result.stdout or "").splitlines())
                if re.search(r"\b\d+ passed\b", line)
            ),
            "pytest passed; detailed output suppressed",
        )
        print(json.dumps({"coverage_tests": "pass", "summary": terminal}))
        export = subprocess.run(
            [sys.executable, "-m", "coverage", "json", "-o", str(raw_json)],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if export.returncode:
            raise RuntimeError(f"coverage_json_failed:{export.stderr[-500:]}")
        report = summarize_coverage(
            json.loads(raw_json.read_text(encoding="utf-8")),
            source_commit=source_commit,
        )
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, sort_keys=True))
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.source_commit, args.output))


if __name__ == "__main__":
    main()
