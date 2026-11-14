"""Build a paired, synthetic manual-versus-assisted workflow protocol."""

SIMULATED_AGENT_MS = {
    "transcription": 900,
    "fact_extraction": 500,
    "drafting": 300,
}


def build_comparison(task_manifest):
    if (
        not isinstance(task_manifest, dict)
        or task_manifest.get("schema_version") != "scripted_correction_tasks_v1"
    ):
        raise ValueError("scripted_correction_manifest_required")
    tasks = task_manifest.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("scripted_correction_tasks_required")
    task_ids = [task.get("task_id") for task in tasks if isinstance(task, dict)]
    if (
        len(task_ids) != len(tasks)
        or not all(task_ids)
        or len(set(task_ids)) != len(task_ids)
    ):
        raise ValueError("scripted_task_ids_must_be_unique")

    paired_tasks = []
    for task in tasks:
        for key in (
            "correction_kind",
            "source_ref",
            "source_text",
            "before_text",
            "after_text",
        ):
            if not isinstance(task.get(key), str) or not task[key].strip():
                raise ValueError("paired_task_source_and_states_required")
        paired_tasks.append(
            {
                "task_id": task["task_id"],
                "correction_kind": task["correction_kind"],
                "source_ref": task["source_ref"],
                "source_text": task["source_text"],
                "shared_initial_note_state": task["before_text"],
                "expected_correction": task["after_text"],
                "manual_only": {
                    "assistive_proposal": None,
                    "agent_time_ms": None,
                    "scripted_agent_time_ms": 0,
                },
                "assisted": {
                    "assistive_proposal": task["after_text"],
                    "proposal_class": "pre_scripted_ideal_stimulus_not_model_output",
                    "scripted_agent_time_ms": dict(SIMULATED_AGENT_MS),
                    "total_scripted_agent_time_ms": sum(SIMULATED_AGENT_MS.values()),
                    "observed_agent_time_ms": None,
                },
            }
        )

    return {
        "schema_version": "paired_synthetic_flow_comparison_v1",
        "scenario_set_id": task_manifest.get("scenario_set_id"),
        "source_truth": "evaluation/scenarios/offline-encounters-v1/scripted-correction-tasks.json",
        "comparison_unit": "same_task_id_and_source_state_paired_across_both_arms",
        "arms": ["manual_only", "assisted_scripted_stimulus"],
        "timing_policy": {
            "simulated_agent_profile": "fixed_demo_profile_v1",
            "simulated_stage_ms": dict(SIMULATED_AGENT_MS),
            "measured_model_runtime_ms": None,
            "clinician_active_time_ms": None,
            "clinical_productivity_estimate": None,
            "time_saved_claim": None,
        },
        "outcomes_to_record": [
            "task_completion",
            "source_evidence_preserved",
            "correction_matches_expected_source",
            "interaction_errors",
            "script_wall_time_ms",
            "observed_agent_runtime_ms_when_a_real_candidate_is_used",
        ],
        "human_observations": 0,
        "clinical_acceptance": False,
        "clinical_release_authorized": False,
        "tasks": paired_tasks,
    }
