import pytest

from services.scripted_correction_tasks import TASKS, simulate_correction_tasks


def test_scripted_correction_replay_covers_required_clinical_edit_classes():
    result = simulate_correction_tasks()

    assert result["task_count"] == 4
    assert result["passed"] == 4
    assert result["human_observations"] == 0
    assert result["clinical_acceptance"] is False
    assert result["all_proposals_unapproved"] is True
    assert {row["correction_kind"] for row in result["outcomes"]} == {
        "medication_dose",
        "add_omitted_source_fact",
        "assertion_negation",
        "speaker_attribution",
    }
    assert all(row["source_evidence_linked"] for row in result["outcomes"])
    assert all(row["proposal_status"] == "unapproved" for row in result["outcomes"])


@pytest.mark.parametrize(
    ("field", "value"),
    [("source_ref", ""), ("after_text", "fabricated fact")],
)
def test_scripted_correction_fails_closed_on_missing_source_or_wrong_correction(
    field, value
):
    task = dict(TASKS[0])
    task[field] = value
    if field == "source_ref":
        with pytest.raises(ValueError, match="identity_and_source"):
            simulate_correction_tasks([task])
    else:
        result = simulate_correction_tasks([task])
        assert result["passed"] == 0
        assert result["outcomes"][0]["correction_matches_source"] is False


def test_duplicate_script_identity_is_rejected():
    with pytest.raises(ValueError, match="identity_and_source"):
        simulate_correction_tasks([TASKS[0], TASKS[0]])
