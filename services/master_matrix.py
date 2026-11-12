"""Build an honest machine-readable execution matrix from the master ledger."""

import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "evaluation/master-task-ledger.json"
SECTION_ID = re.compile(r"^(\d{2})\s")


def build(ledger=None, source_commit=None):
    raw_ledger = ledger is None
    if ledger is None:
        ledger_bytes = LEDGER.read_bytes()
        ledger = json.loads(ledger_bytes.decode("utf-8"))
    else:
        ledger_bytes = json.dumps(ledger, sort_keys=True).encode("utf-8")
    tasks = ledger["tasks"]
    if ledger.get("total") != len(tasks) or len({t["id"] for t in tasks}) != len(tasks):
        raise ValueError("master_ledger_invalid")
    section_ids = {}
    for task in tasks:
        match = SECTION_ID.match(task["section"])
        if not match:
            raise ValueError("section_id_missing")
        section_ids[task["id"]] = int(match.group(1))
    sections = sorted(set(section_ids.values()))
    predecessors = {
        section: (sections[i - 1] if i else None) for i, section in enumerate(sections)
    }
    rows = []
    for task in tasks:
        section = section_ids[task["id"]]
        previous = predecessors[section]
        rows.append(
            {
                "id": task["id"],
                "section": section,
                "owner": "AI agent",
                "priority": task["priority"],
                "status": task["status"],
                "description": task["description"],
                "suggested_after_sections": [previous] if previous is not None else [],
                "task_dependencies": None,
                "task_dependency_mapping": "unmapped_pending_manual_audit",
                "executable_evidence": task.get("evidence", []),
                "last_run_sha": task.get("source_commit"),
                "test_results": task.get("test_results", []),
                "failure_or_blocker": task.get("blocker"),
            }
        )
    if source_commit is None:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    return {
        "schema_version": "master_implementation_matrix_v1",
        "source_commit": source_commit,
        "ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        "ledger_hash_representation": "raw_source_bytes"
        if raw_ledger
        else "canonical_json",
        "dependency_policy": "numbered section order is a planning heuristic, not an audited dependency graph",
        "owner": "AI agent",
        "total": len(rows),
        "tasks": rows,
        "clinical_release_authorized": False,
    }


def write(path):
    output = Path(path)
    if output.exists():
        raise FileExistsError("matrix_versions_are_immutable")
    output.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(write(args.output))
