"""Deterministic replay of scripted clinical correction tasks.

These fixtures exercise correction bookkeeping only. They are not observations of
clinician behavior and do not establish clinical correctness.
"""

from copy import deepcopy
import json
from pathlib import Path

from services.role_correction import preview as preview_role_correction


_TASKS_PATH = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "scenarios"
    / "offline-encounters-v1"
    / "scripted-correction-tasks.json"
)
TASKS = tuple(json.loads(_TASKS_PATH.read_text(encoding="utf-8"))["tasks"])


def simulate_correction_tasks(tasks=TASKS):
    """Replay scripted edits and return auditable outcomes with approval withheld."""
    if not isinstance(tasks, (list, tuple)):
        raise ValueError("correction_tasks_must_be_a_sequence")
    outcomes = []
    seen = set()
    for original in tasks:
        if not isinstance(original, dict):
            raise ValueError("correction_task_must_be_an_object")
        task = deepcopy(original)
        task_id = task.get("task_id")
        source_ref = task.get("source_ref")
        if not task_id or task_id in seen or not source_ref:
            raise ValueError("correction_task_identity_and_source_required")
        seen.add(task_id)
        source_text = task.get("source_text")
        before_text = task.get("before_text")
        after_text = task.get("after_text")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (source_text, before_text, after_text)
        ):
            raise ValueError("correction_task_text_required")

        if task.get("correction_kind") == "speaker_attribution":
            role_change = preview_role_correction(
                [
                    {
                        "id": task_id,
                        "speaker": "speaker-2",
                        "role": "unknown",
                        "source_ref": source_ref,
                    }
                ],
                {"speaker-2": "clinician"},
            )
            valid = (
                len(role_change["changes"]) == 1
                and role_change["changes"][0]["source_ref"] == source_ref
                and after_text == "speaker-2 is clinician"
                and role_change["approval_required"]
            )
        else:
            valid = after_text == source_text

        outcomes.append(
            {
                "task_id": task_id,
                "correction_kind": task["correction_kind"],
                "instruction": task.get("instruction", ""),
                "source_ref": source_ref,
                "before_text": before_text,
                "after_text": after_text,
                "source_text": source_text,
                "correction_matches_source": valid,
                "source_evidence_linked": bool(source_ref),
                "proposal_status": "unapproved",
                "approval_granted": False,
                "execution_kind": "deterministic_script_replay",
            }
        )
    return {
        "schema_version": "scripted_correction_task_replay_v1",
        "task_count": len(outcomes),
        "passed": sum(row["correction_matches_source"] for row in outcomes),
        "all_proposals_unapproved": all(
            not row["approval_granted"] for row in outcomes
        ),
        "outcomes": outcomes,
        "human_observations": 0,
        "clinical_acceptance": False,
    }
