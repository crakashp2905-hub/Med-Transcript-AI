"""Run synthetic adversarial input-mutation checks for critical workflow gates.

This is a behavioral attack-case score, not source-code mutation testing or
clinical validation. It exercises existing application tests with deliberately
mutated approval, identity, evidence, and retention inputs.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


TARGETS = (
    "tests/test_safety_properties.py::test_synthetic_approval_mutations_never_pass_without_their_required_review",
    "tests/test_foundation.py::test_other_tenant_and_unassigned_clinician_cannot_access",
    "tests/test_route_authorization.py::test_route_authorization_blocks_scope_mutations",
    "tests/test_router_contracts.py::test_all_identity_routes_reject_missing_auth_and_viewer_writes",
    "tests/test_review_workflow.py::test_false_or_cross_version_evidence_is_rejected",
    "tests/test_proposal_integrity.py::test_changed_persisted_proposals_are_rejected_before_display",
    "tests/test_proposal_integrity.py::test_rehashed_proposal_cannot_borrow_another_encounters_source",
    "tests/test_retention_state.py::test_browser_retention_failures_never_claim_success",
    "tests/test_adversarial_replay.py::test_replay_marks_approval_stale_after_any_single_input_change",
)


def category_for(case_id):
    if "test_synthetic_approval_mutations" in case_id:
        return "evidence" if "[evidence]" in case_id else "approval"
    if "test_other_tenant_and_unassigned" in case_id:
        return "authorization"
    if "test_route_authorization_blocks_scope_mutations" in case_id:
        return "authorization"
    if "test_all_identity_routes_reject_missing_auth" in case_id:
        return "authorization"
    if "test_false_or_cross_version_evidence" in case_id:
        return "evidence"
    if "test_changed_persisted_proposals" in case_id:
        return "evidence"
    if "test_rehashed_proposal_cannot_borrow" in case_id:
        return "evidence"
    if "test_browser_retention_failures" in case_id:
        return "retention"
    if "test_replay_marks_approval_stale" in case_id:
        return "stale_approval"
    raise ValueError("unclassified_mutation_case")


def read_junit(path):
    root = ET.parse(path).getroot()
    rows = []
    for case in root.iter("testcase"):
        case_id = f"{case.get('classname', '')}::{case.get('name', '')}"
        child = next(
            (item for item in case if item.tag in {"failure", "error", "skipped"}),
            None,
        )
        outcome = "passed" if child is None else child.tag
        rows.append(
            {
                "id": case_id,
                "category": category_for(case_id),
                "outcome": outcome,
            }
        )
    if not rows:
        raise ValueError("mutation_campaign_no_test_cases")
    return rows


def summarize(rows, source_commit):
    killed = sum(row["outcome"] == "passed" for row in rows)
    survivors = [row["id"] for row in rows if row["outcome"] in {"failure", "error"}]
    not_executed = [row["id"] for row in rows if row["outcome"] == "skipped"]
    return {
        "schema_version": "critical_behavior_mutation_report_v1",
        "source_commit": source_commit,
        "mutation_kind": "synthetic_adversarial_input_mutation",
        "score": {
            "killed_scenarios": killed,
            "total_scenarios": len(rows),
            "percent": round(killed * 100 / len(rows), 2),
            "definition": "A scenario is killed when its targeted test passes by rejecting the mutated input or stale state.",
        },
        "cases": rows,
        "surviving_mutations": survivors,
        "not_executed": not_executed,
        "source_code_mutation_score": "not_measured",
        "limitations": [
            "The identity-route test aggregates 50 or more route assertions into one test case.",
            "This developer-authored synthetic campaign is not independent clinical validation.",
            "A source-code mutation engine was unavailable locally; the reported score is for adversarial input scenarios only.",
        ],
        "clinical_release_authorized": False,
    }


def run_campaign(source_commit):
    with tempfile.TemporaryDirectory(prefix="med-transcript-mutation-") as temp:
        junit = Path(temp) / "mutation-results.xml"
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *TARGETS,
            f"--basetemp={Path(temp) / 'pytest'}",
            f"--junitxml={junit}",
        ]
        env = {**os.environ, "MED_TRANSCRIPT_OFFLINE": "1"}
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                env=env,
                check=False,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            return {
                "schema_version": "critical_behavior_mutation_report_v1",
                "source_commit": source_commit,
                "mutation_kind": "synthetic_adversarial_input_mutation",
                "status": "timed_out",
                "score": {"killed_scenarios": 0, "total_scenarios": 0, "percent": 0},
                "cases": [],
                "surviving_mutations": [],
                "not_executed": list(TARGETS),
                "source_code_mutation_score": "not_measured",
                "clinical_release_authorized": False,
            }
        if not junit.is_file():
            return {
                "schema_version": "critical_behavior_mutation_report_v1",
                "source_commit": source_commit,
                "mutation_kind": "synthetic_adversarial_input_mutation",
                "status": "failed_to_collect",
                "score": {"killed_scenarios": 0, "total_scenarios": 0, "percent": 0},
                "cases": [],
                "surviving_mutations": [],
                "not_executed": list(TARGETS),
                "source_code_mutation_score": "not_measured",
                "clinical_release_authorized": False,
            }
        rows = read_junit(junit)
        result = summarize(rows, source_commit)
        result["status"] = (
            "pass"
            if completed.returncode == 0 and not result["not_executed"]
            else "fail"
        )
        # Keep reports free of assertion values and captured clinical text.
        result["pytest_exit_code"] = completed.returncode
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    report = run_campaign(args.source_commit)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError("mutation_campaign_report_exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
