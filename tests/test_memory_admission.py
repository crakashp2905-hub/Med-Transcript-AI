import pytest

from services.memory_admission import admit


def test_memory_pressure_queues_before_oom_and_preserves_source_state():
    result = admit(requested_bytes=100, available_bytes=50, completed_source_state=True)
    assert result["action"] == "queue"
    assert result["source_state_preserved"] is True


def test_memory_admission_runs_when_capacity_is_available():
    assert admit(requested_bytes=50, available_bytes=100)["action"] == "run"
    with pytest.raises(ValueError):
        admit(requested_bytes=-1, available_bytes=1)
