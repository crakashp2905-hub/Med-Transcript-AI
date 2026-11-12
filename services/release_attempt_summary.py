"""Publish an exact-source CI and offline-acceptance freshness summary."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def build_summary(
    *, source_commit, run_id, jobs, acceptance=None, acceptance_sha256=None
):
    if not isinstance(source_commit, str) or len(source_commit) != 40:
        raise ValueError("summary_source_commit_invalid")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("summary_run_id_missing")
    required_jobs = {"python_matrix", "frontend", "postgres", "container"}
    if set(jobs) != required_jobs or any(
        status not in {"success", "failure", "cancelled", "skipped"}
        for status in jobs.values()
    ):
        raise ValueError("summary_ci_job_set_invalid")
    ci_pass = all(status == "success" for status in jobs.values())
    acceptance_summary = {
        "status": "not_available",
        "source_commit": None,
        "checks": {},
    }
    if isinstance(acceptance, dict):
        acceptance_summary = {
            "status": "stale"
            if acceptance.get("source_commit") != source_commit
            else "blocked",
            "source_commit": acceptance.get("source_commit"),
            "checks": {},
        }
        checks = acceptance.get("checks", {})
        if acceptance.get("source_commit") == source_commit and isinstance(
            checks, dict
        ):
            statuses = {
                name: value.get("status") if isinstance(value, dict) else value
                for name, value in checks.items()
            }
            acceptance_summary["checks"] = statuses
            if statuses and all(status == "pass" for status in statuses.values()):
                acceptance_summary["status"] = "pass"
    return {
        "schema_version": "release_attempt_summary_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit,
        "ci_run_id": run_id,
        "ci_status": "pass" if ci_pass else "fail",
        "ci_jobs": jobs,
        "python_matrix_note": "The Python test matrix result is conservative and applies to both configured extras lanes.",
        "offline_acceptance": acceptance_summary,
        "offline_acceptance_sha256": acceptance_sha256,
        "clinical_release_authorized": False,
    }


def markdown(report):
    lines = [
        "# Release attempt summary",
        "",
        f"**Source commit:** `{report['source_commit']}`  ",
        f"**GitHub Actions run:** `{report['ci_run_id']}`  ",
        f"**CI status:** `{report['ci_status'].upper()}`",
        "",
        "| CI check | Result |",
        "| --- | --- |",
    ]
    lines.extend(f"| {name} | {status} |" for name, status in report["ci_jobs"].items())
    lines += [
        "",
        "## Offline acceptance",
        "",
        f"Status: **{report['offline_acceptance']['status'].upper()}**.",
    ]
    if report["offline_acceptance"].get("source_commit"):
        lines.append(
            f"Report source commit: `{report['offline_acceptance']['source_commit']}`."
        )
    if report.get("offline_acceptance_sha256"):
        lines.append(f"Report SHA-256: `{report['offline_acceptance_sha256']}`.")
    checks = report["offline_acceptance"].get("checks", {})
    if checks:
        lines += ["", "| Acceptance check | Result |", "| --- | --- |"]
        lines.extend(f"| {name} | {status} |" for name, status in checks.items())
    lines += [
        "",
        "Clinical release authorization: **false**. CI success and offline acceptance do not constitute clinical approval.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--python-matrix-status", required=True)
    parser.add_argument("--frontend-status", required=True)
    parser.add_argument("--postgres-status", required=True)
    parser.add_argument("--container-status", required=True)
    parser.add_argument("--acceptance-report")
    parser.add_argument("--output", required=True)
    parser.add_argument("--step-summary")
    args = parser.parse_args()
    acceptance = None
    acceptance_sha = None
    if args.acceptance_report:
        path = Path(args.acceptance_report)
        acceptance_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        acceptance = json.loads(path.read_text(encoding="utf-8"))
    report = build_summary(
        source_commit=args.source_commit,
        run_id=args.run_id,
        jobs={
            "python_matrix": args.python_matrix_status,
            "frontend": args.frontend_status,
            "postgres": args.postgres_status,
            "container": args.container_status,
        },
        acceptance=acceptance,
        acceptance_sha256=acceptance_sha,
    )
    Path(args.output).write_text(markdown(report), encoding="utf-8")
    if args.step_summary:
        with Path(args.step_summary).open("a", encoding="utf-8") as summary:
            summary.write(markdown(report))
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["ci_status"] == "pass" else 1)


if __name__ == "__main__":
    main()
