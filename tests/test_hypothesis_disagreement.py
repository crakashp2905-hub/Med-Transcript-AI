import pytest

from services.asr.hypothesis_disagreement import compare_hypotheses


def test_disagreement_reports_medical_substitutions_without_selecting_text():
    hypotheses = [
        {"backend_id": "engine-a", "text": "Patient denies taking 5 mg metformin."},
        {"backend_id": "engine-b", "text": "Patient takes 15 mg metformin."},
    ]
    report = compare_hypotheses(hypotheses)
    pair = report["pairs"][0]
    assert pair["normalized_edit_count"] == 3
    assert pair["normalized_disagreement_rate"] > 0
    assert report["score_kind"] == "uncalibrated_text_disagreement_diagnostic"
    assert report["agreement_is_not_truth"]
    assert report["candidate_selection_performed"] is False
    assert hypotheses[0]["text"] == "Patient denies taking 5 mg metformin."


def test_agreement_is_reported_as_zero_disagreement_not_as_correctness():
    report = compare_hypotheses(
        [
            {"backend_id": "one", "text": "No penicillin allergy"},
            {"backend_id": "two", "text": "No penicillin allergy"},
        ]
    )
    assert report["pairs"][0]["normalized_disagreement_rate"] == 0
    assert report["agreement_is_not_truth"]


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"backend_id": "one", "text": "only one"}],
        [
            {"backend_id": "duplicate", "text": "a"},
            {"backend_id": "duplicate", "text": "b"},
        ],
    ],
)
def test_disagreement_rejects_incomplete_or_duplicate_engines(rows):
    with pytest.raises(ValueError):
        compare_hypotheses(rows)
