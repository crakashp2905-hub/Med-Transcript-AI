import pytest

from services.queue_dashboard import snapshot


def test_queue_dashboard_exposes_operational_and_consent_fields():
    result = snapshot(
        stage="asr",
        attempts=2,
        lease_owner="worker-1",
        timeout_seconds=30,
        consent_state="active",
    )
    assert result["stage"] == "asr" and result["attempts"] == 2
    assert result["lease_owner"] == "worker-1" and result["timeout_seconds"] == 30
    assert result["revoked"] is False


def test_queue_dashboard_rejects_invalid_state():
    with pytest.raises(ValueError):
        snapshot(
            stage="asr",
            attempts=-1,
            lease_owner=None,
            timeout_seconds=1,
            consent_state="active",
        )
