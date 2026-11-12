import pytest

from services.stress_scenario import record


def test_stress_scenario_separates_transport_from_accuracy():
    result = record(duration_minutes=30, channels=8, transport_seconds=4, wer=0.04)
    assert result["transport_accuracy_separate"] is True
    assert result["normalized_wer"] == 0.04


def test_stress_scenario_rejects_wrong_shape():
    with pytest.raises(ValueError):
        record(duration_minutes=10, channels=8, transport_seconds=1, wer=0)
