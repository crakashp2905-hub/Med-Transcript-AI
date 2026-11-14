"""Build a transparent, non-authorizing multi-axis readiness scorecard."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "evaluation/master-task-ledger.json"
SECTION_ID = re.compile(r"^(\d{2})\s")

# These are planning groupings, not claims that every task in a section has one
# exclusive owner. The ledger section is the reproducible classification key.
AXIS_SECTIONS = {
    "research": {3, 4, 5, 6, 7, 8, 9, 10, 11},
    "engineering": {0, 1, 2, 12, 13, 16, 17},
    "product": {14, 15, 18},
}
PRIORITY_WEIGHTS = {"P0": 3, "P1": 2, "P2": 1}
STATUS_CREDIT = {
    "verified": 1.0,
    "implemented": 0.5,
    "not_started": 0.0,
    "blocked_missing_asset": 0.0,
    "blocked_external_evidence": 0.0,
    "failed": 0.0,
}


def build(ledger=None, source_commit=None):
    raw_ledger = ledger is None
    if ledger is None:
        ledger_bytes = LEDGER.read_bytes()
        ledger = json.loads(ledger_bytes.decode("utf-8"))
    else:
        ledger_bytes = json.dumps(ledger, sort_keys=True).encode("utf-8")
    tasks = ledger.get("tasks")
    if (
        not isinstance(tasks, list)
        or ledger.get("total") != len(tasks)
        or len({task.get("id") for task in tasks}) != len(tasks)
    ):
        raise ValueError("readiness_ledger_invalid")

    axes = {name: [] for name in AXIS_SECTIONS}
    for task in tasks:
        match = SECTION_ID.match(task.get("section", ""))
        if not match:
            raise ValueError("readiness_section_id_missing")
        section = int(match.group(1))
        axis = next(
            (name for name, sections in AXIS_SECTIONS.items() if section in sections),
            None,
        )
        if axis is None:
            raise ValueError("readiness_section_unclassified")
        priority = task.get("priority")
        status = task.get("status")
        if priority not in PRIORITY_WEIGHTS or status not in STATUS_CREDIT:
            raise ValueError("readiness_task_state_invalid")
        axes[axis].append(
            {
                "id": task["id"],
                "priority": priority,
                "priority_weight": PRIORITY_WEIGHTS[priority],
                "status": status,
                "credit": STATUS_CREDIT[status],
                "weighted_credit": PRIORITY_WEIGHTS[priority] * STATUS_CREDIT[status],
                "blocker": task.get("blocker"),
            }
        )

    summaries = {}
    for axis, rows in axes.items():
        total_weight = sum(row["priority_weight"] for row in rows)
        earned_weight = sum(row["weighted_credit"] for row in rows)
        summaries[axis] = {
            "task_count": len(rows),
            "priority_weight_total": total_weight,
            "priority_weight_earned": earned_weight,
            "weighted_readiness_percent": round(100 * earned_weight / total_weight, 2)
            if total_weight
            else None,
            "status_counts": {
                status: sum(row["status"] == status for row in rows)
                for status in STATUS_CREDIT
                if any(row["status"] == status for row in rows)
            },
            "tasks": rows,
        }

    if source_commit is None:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    return {
        "schema_version": "readiness_scorecard_v1",
        "source_commit": source_commit,
        "ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        "ledger_hash_representation": "raw_source_bytes"
        if raw_ledger
        else "canonical_json",
        "weighting": {
            "priority": PRIORITY_WEIGHTS,
            "status_credit": STATUS_CREDIT,
            "axis_section_ids": {
                axis: sorted(sections) for axis, sections in AXIS_SECTIONS.items()
            },
            "interpretation": "weighted ledger completion signal; not clinical validity, deployment readiness, or release authorization",
        },
        "axes": summaries,
        "clinical_release_authorized": False,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError("scorecard_versions_are_immutable")
    output.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
    print(output)
