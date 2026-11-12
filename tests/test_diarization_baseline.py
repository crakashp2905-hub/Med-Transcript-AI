from services.diarization_baseline import WEIGHTED_DER_BASELINE, baseline_report


def test_weighted_der_baseline_is_pinned_without_reliability_claim():
    result = baseline_report()
    assert WEIGHTED_DER_BASELINE == 0.5091 and result["weighted_der"] == 0.5091
    assert result["heuristic_reliable"] is False
    assert result["requires_independent_scoring"] is True
