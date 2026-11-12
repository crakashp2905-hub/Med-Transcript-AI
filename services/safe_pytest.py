"""Run pytest while keeping assertions, source excerpts and case text out of logs."""

import argparse
import json
import re
import subprocess
import sys


SUMMARY = re.compile(
    r"\b\d+ (?:passed|failed|skipped|warnings?|errors?|deselected|xfailed|xpassed)\b"
)
FAILURE = re.compile(r"^FAILED ([A-Za-z0-9_./-]+)::([A-Za-z_][A-Za-z0-9_]*)")


def run(paths, *, runner=subprocess.run):
    result = runner(
        [sys.executable, "-m", "pytest", "-q", *paths],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = (result.stdout or "").splitlines()
    terminal = next((line for line in reversed(lines) if SUMMARY.search(line)), "")
    safe_counts = ", ".join(SUMMARY.findall(terminal)) or "summary unavailable"
    failed_tests = sorted(
        {
            f"{match.group(1)}::{match.group(2)}"
            for line in lines
            if (match := FAILURE.match(line))
        }
    )[:50]
    status = "pass" if result.returncode == 0 else "fail"
    print(
        json.dumps(
            {
                "check": "pytest",
                "status": status,
                "exit_code": result.returncode,
                "summary": safe_counts,
                "failed_tests": failed_tests,
                "raw_output_logged": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Pytest files or node IDs")
    args = parser.parse_args()
    raise SystemExit(run(args.paths))


if __name__ == "__main__":
    main()
