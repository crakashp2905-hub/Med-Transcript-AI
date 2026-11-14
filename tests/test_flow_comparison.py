import json
from pathlib import Path

import pytest

from services.flow_comparison import build_comparison


ROOT = Path(__file__).resolve().parents[1]
TASKS_PATH = (
    ROOT / "evaluation/scenarios/offline-encounters-v1/scripted-correction-tasks.json"
)
PROTOCOL_PATH = ROOT / "evaluation/protocols/manual-assisted-comparison-v1.json"


def test_comparison_pairs_identical_tasks_and_marks_all_assisted_timings_simulated():
    manifest = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    expected = build_comparison(manifest)
    recorded = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))

    assert recorded == expected
    assert len(recorded["tasks"]) == 4
    for task in recorded["tasks"]:
        assert task["manual_only"]["assistive_proposal"] is None
        assert task["manual_only"]["agent_time_ms"] is None
        assert (
            task["assisted"]["proposal_class"]
            == "pre_scripted_ideal_stimulus_not_model_output"
        )
        assert task["assisted"]["observed_agent_time_ms"] is None
        assert task["source_text"]
        assert task["source_ref"]
        assert task["expected_correction"] == task["assisted"]["assistive_proposal"]
    assert recorded["timing_policy"]["clinician_active_time_ms"] is None
    assert recorded["timing_policy"]["time_saved_claim"] is None
    assert recorded["human_observations"] == 0
    assert recorded["clinical_acceptance"] is False


def test_comparison_rejects_duplicate_task_ids():
    manifest = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    manifest["tasks"].append(dict(manifest["tasks"][0]))
    with pytest.raises(ValueError, match="unique"):
        build_comparison(manifest)
