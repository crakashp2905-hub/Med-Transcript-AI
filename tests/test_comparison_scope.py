import pytest

from services.comparison_scope import prepare


def test_comparison_keeps_failed_candidates_visible_and_ranks_only_complete_same_scope():
    value = prepare(
        [
            {
                "candidate_id": "good",
                "dataset_id": "d1",
                "task_scope": "asr",
                "evaluation_scope": "text_only",
                "status": "completed",
                "normalized_wer": 0.1,
            },
            {
                "candidate_id": "failed",
                "dataset_id": "d1",
                "task_scope": "asr",
                "evaluation_scope": "text_only",
                "status": "runtime_failed",
            },
        ]
    )
    assert (
        value["ranked_candidates"] == ["good"] and value["failed_or_unranked_visible"]
    )
    assert (
        next(row for row in value["rows"] if row["candidate_id"] == "failed")["rank"]
        is None
    )


def test_comparison_rejects_cross_dataset_rows():
    rows = [
        {
            "candidate_id": "a",
            "dataset_id": "d1",
            "task_scope": "asr",
            "evaluation_scope": "text",
        },
        {
            "candidate_id": "b",
            "dataset_id": "d2",
            "task_scope": "asr",
            "evaluation_scope": "text",
        },
    ]
    with pytest.raises(ValueError, match="cross_dataset_comparison_forbidden"):
        prepare(rows)
