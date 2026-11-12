import pytest

from services.model_init_metrics import record


def test_model_init_metrics_separate_cold_and_warm_measurements():
    result = record(cold_seconds=10, warm_seconds=2, cold_bytes=100, warm_bytes=80)
    assert result["warm_speedup"] == 5
    assert result["cache_effect"] is True


def test_model_init_metrics_reject_negative_values():
    with pytest.raises(ValueError):
        record(cold_seconds=-1, warm_seconds=1, cold_bytes=1, warm_bytes=1)
