import pytest

from services.workflow_metrics import record


def test_workflow_metrics_include_quality_runtime_memory_and_corrections():
    result = record(
        critical_misses=0,
        benign_false_blocks=1,
        covered=9,
        total=10,
        runtime_seconds=2,
        memory_bytes=100,
        corrections=3,
    )
    assert result["coverage"] == 0.9
    assert result["reviewer_corrections"] == 3


def test_workflow_metrics_reject_invalid_coverage():
    with pytest.raises(ValueError):
        record(
            critical_misses=0,
            benign_false_blocks=0,
            covered=11,
            total=10,
            runtime_seconds=1,
            memory_bytes=1,
            corrections=0,
        )
