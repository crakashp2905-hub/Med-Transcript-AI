import pytest

from services.uncertainty_report import report


def test_uncertainty_report_preserves_exact_denominator_and_synthetic_limit():
    result = report(correct=8, total=10, interval_low=0.5, interval_high=0.95, synthetic=True)
    assert result['denominator_exact'] is True and result['paired'] is True
    assert result['evidence_class'] == 'mechanistic_synthetic'


def test_uncertainty_report_rejects_invalid_counts():
    with pytest.raises(ValueError):
        report(correct=11, total=10, interval_low=0, interval_high=1)
