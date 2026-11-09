import pytest

from services.resource_arbiter import decide


def test_resource_arbiter_defers_competing_model_request_before_oversubscription():
    result = decide(active_bytes=80, request_bytes=30, capacity_bytes=100)
    assert result['action'] == 'defer'
    assert result['oversubscribed'] is True


def test_resource_arbiter_admits_within_capacity():
    assert decide(active_bytes=20, request_bytes=30, capacity_bytes=100)['action'] == 'admit'
    with pytest.raises(ValueError):
        decide(active_bytes=-1, request_bytes=1, capacity_bytes=1)
