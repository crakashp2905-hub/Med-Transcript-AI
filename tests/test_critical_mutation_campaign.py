import pytest

from services.critical_mutation_campaign import category_for, summarize


@pytest.mark.parametrize(
    ("case_id", "expected"),
    [
        (
            "tests.test_safety_properties::test_synthetic_approval_mutations[evidence]",
            "evidence",
        ),
        (
            "tests.test_safety_properties::test_synthetic_approval_mutations[dose]",
            "approval",
        ),
        (
            "tests.test_foundation::test_other_tenant_and_unassigned_clinician[b]",
            "authorization",
        ),
        (
            "tests.test_proposal_integrity::test_changed_persisted_proposals[draft]",
            "evidence",
        ),
        (
            "tests.test_retention_state::test_browser_retention_failures[quota]",
            "retention",
        ),
        (
            "tests.test_adversarial_replay::test_replay_marks_approval_stale[source]",
            "stale_approval",
        ),
    ],
)
def test_campaign_assigns_critical_policy_categories(case_id, expected):
    assert category_for(case_id) == expected


def test_campaign_score_names_survivors_and_skips_without_hiding_them():
    rows = [
        {"id": "approval-dose", "category": "approval", "outcome": "passed"},
        {"id": "tenant-bypass", "category": "authorization", "outcome": "failure"},
        {"id": "retention-skip", "category": "retention", "outcome": "skipped"},
    ]

    report = summarize(rows, "a" * 40)

    assert report["score"]["killed_scenarios"] == 1
    assert report["score"]["total_scenarios"] == 3
    assert report["score"]["percent"] == pytest.approx(33.33)
    assert report["surviving_mutations"] == ["tenant-bypass"]
    assert report["not_executed"] == ["retention-skip"]
    assert report["source_code_mutation_score"] == "not_measured"
