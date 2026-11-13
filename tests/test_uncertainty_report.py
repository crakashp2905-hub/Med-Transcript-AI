import pytest

from services.uncertainty_report import report


def test_uncertainty_report_preserves_exact_denominator_and_synthetic_limit():
    result = report(
        correct=8,
        total=10,
        interval_low=0.5,
        interval_high=0.95,
        synthetic=True,
        paired=True,
    )
    assert result["denominator_exact"] is True and result["paired"] is True
    assert result["evidence_class"] == "mechanistic_synthetic"
    assert result["pairing_status"] == "caller_declared"
    assert result["uncertainty_kind"] == "descriptive_interval_not_asr_confidence"
    assert result["calibrated"] is False and result["probability_estimate"] is None


def test_unpaired_interval_does_not_claim_calibration_or_probability():
    result = report(correct=2, total=4, interval_low=0.1, interval_high=0.8)
    assert result["paired"] is False
    assert result["pairing_status"] == "not_established"
    assert result["calibrated"] is False
    assert result["probability_estimate"] is None


def test_uncertainty_report_rejects_invalid_counts():
    with pytest.raises(ValueError):
        report(correct=11, total=10, interval_low=0, interval_high=1)


def test_uncertainty_report_rejects_unbounded_interval_or_pairing_flag():
    with pytest.raises(ValueError, match="invalid_interval"):
        report(correct=1, total=2, interval_low=0, interval_high=1.1)
    with pytest.raises(ValueError, match="invalid_pairing_declaration"):
        report(correct=1, total=2, interval_low=0, interval_high=1, paired=1)
