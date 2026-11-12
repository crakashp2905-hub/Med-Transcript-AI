import pytest

from services.fault_injection import inject


def test_fault_injection_preserves_source_and_blocks_publication():
    for fault in (
        "slow_disk",
        "write_failure",
        "process_kill",
        "database_busy",
        "model_absent",
    ):
        result = inject(fault)
        assert result["source_state_preserved"] is True
        assert result["publication_allowed"] is False


def test_fault_injection_marks_retryable_faults():
    assert inject("database_busy")["retryable"] is True
    assert inject("model_absent")["retryable"] is False
    with pytest.raises(ValueError):
        inject("unknown")
