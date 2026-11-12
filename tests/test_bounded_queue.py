import pytest

from services.bounded_queue import admit


def test_bounded_queue_rejects_overload_explicitly():
    result = admit(queued=10, capacity=10)
    assert result["accepted"] is False and result["action"] == "reject"


def test_bounded_queue_accepts_when_capacity_exists():
    assert admit(queued=1, capacity=2)["action"] == "enqueue"
    with pytest.raises(ValueError):
        admit(queued=-1, capacity=2)
