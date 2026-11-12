import pytest

from services.regression_gate import compare


def test_safety_regression_blocks_even_when_wer_improves():
    baseline = {
        "dataset_id": "synthetic-v1",
        "normalized_wer": 0.10,
        "critical_misses": 0,
        "omissions": 1,
        "false_blocks": 2,
    }
    candidate = {
        "dataset_id": "synthetic-v1",
        "normalized_wer": 0.08,
        "critical_misses": 1,
        "omissions": 0,
        "false_blocks": 1,
    }
    result = compare(baseline, candidate)
    assert result["wer_improved"] and result["safety_regressions"] == {
        "critical_misses": 1
    }
    assert result["promotion"] == "blocked"


def test_regression_gate_rejects_incomparable_or_incomplete_vectors():
    base = {
        "dataset_id": "a",
        "normalized_wer": 0.1,
        "critical_misses": 0,
        "omissions": 0,
        "false_blocks": 0,
    }
    with pytest.raises(ValueError, match="incomparable_regression_dataset"):
        compare(base, {**base, "dataset_id": "b"})
    with pytest.raises(ValueError, match="incomplete_regression_vector"):
        compare(base, {"dataset_id": "a", "normalized_wer": 0.1})
