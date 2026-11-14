import pytest

from services.evaluation_distribution import summarize


def test_distribution_reports_pooled_and_case_quantiles_and_worst_slice():
    result = summarize(
        [
            {
                "sample_id": "a",
                "group_id": "visit-1",
                "speaker_role": "patient",
                "noise_condition": "quiet",
                "reference_uncertain": False,
                "reference_words": 10,
                "normalized_edits": 0,
                "status": "completed",
            },
            {
                "sample_id": "b",
                "group_id": "visit-1",
                "speaker_role": "doctor",
                "noise_condition": "quiet",
                "reference_uncertain": False,
                "reference_words": 10,
                "normalized_edits": 2,
                "status": "completed",
            },
            {
                "sample_id": "c",
                "group_id": "visit-2",
                "speaker_role": "patient",
                "noise_condition": "traffic",
                "reference_uncertain": True,
                "reference_words": 10,
                "normalized_edits": 10,
                "status": "failed",
            },
        ]
    )
    assert result["pooled_normalized_wer"] == pytest.approx(0.4)
    assert result["consultation_wer_distribution"]["p50"] == pytest.approx(0.2)
    assert result["consultation_wer_distribution"]["p95"] == pytest.approx(0.92)
    assert result["worst_slices"]["noise_condition"]["worst_slice"] == "traffic"
    assert (
        result["worst_slices"]["noise_condition"]["slices"]["traffic"][
            "failed_case_count"
        ]
        == 1
    )
    assert result["failure_inclusive"] is True


def test_distribution_rejects_duplicate_case_ids_and_impossible_edits():
    row = {
        "sample_id": "a",
        "reference_words": 1,
        "hypothesis_words": 0,
        "normalized_edits": 2,
    }
    with pytest.raises(ValueError, match="metrics_invalid"):
        summarize([row])
    with pytest.raises(ValueError, match="metrics_invalid"):
        summarize([row, row])
