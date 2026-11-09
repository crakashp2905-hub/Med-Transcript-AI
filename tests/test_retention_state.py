import pytest

from services.retention_state import transition


def test_browser_retention_failures_never_claim_success():
    for event in ('quota_exhausted', 'storage_evicted', 'microphone_removed'):
        result = transition(event=event, persisted_bytes=10)
        assert result['state'] == 'retention_failed'
        assert result['retained'] is False


def test_persisted_state_is_explicit():
    assert transition(event='persisted', persisted_bytes=10)['retained'] is True
    with pytest.raises(ValueError):
        transition(event='unknown')
