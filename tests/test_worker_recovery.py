import pytest

from services.worker_recovery import recover


def test_worker_recovery_reacquires_stale_lease_without_publishing():
    result = recover(stage='asr', lease_state='stale', checkpoint={'chunk': 3})
    assert result['action'] == 'reacquire_lease'
    assert result['checkpoint']['chunk'] == 3
    assert result['publish'] is False


def test_worker_recovery_rejects_invalid_lease_state():
    with pytest.raises(ValueError):
        recover(stage='asr', lease_state='bogus', checkpoint={})
