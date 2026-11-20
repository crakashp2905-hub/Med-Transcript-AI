import pytest

from services.stratified_asr_bootstrap import _paired_interval


def test_stratified_bootstrap_resamples_paired_consultation_groups():
    groups = {
        "consultation-1": {
            "clean": {"errors": 1, "reference_words": 10},
            "distracted": {"errors": 2, "reference_words": 10},
        },
        "consultation-2": {
            "clean": {"errors": 0, "reference_words": 10},
            "distracted": {"errors": 1, "reference_words": 10},
        },
        "consultation-3": {
            "clean": {"errors": 3, "reference_words": 10},
            "distracted": {"errors": 4, "reference_words": 10},
        },
        "consultation-4": {
            "clean": {"errors": 2, "reference_words": 10},
            "distracted": {"errors": 2, "reference_words": 10},
        },
    }
    report = _paired_interval(
        groups,
        numerator_key="errors",
        denominator_key="reference_words",
        seed=20261121,
    )
    assert report["clean_rate"] == pytest.approx(0.15)
    assert report["distracted_rate"] == pytest.approx(0.225)
    assert report["distracted_minus_clean"] == pytest.approx(0.075)
    assert report["consultation_groups"] == 4
    assert report["paired_groups"] == sorted(groups)
    assert report["low"] <= report["high"]
