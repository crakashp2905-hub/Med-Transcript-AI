import pytest

from services.workflow_metrics import record, summarize_stage_runs


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


def test_stage_latency_uses_successful_measured_denominator_and_counts_failures():
    result = summarize_stage_runs(
        [
            {"run_id": "1", "status": "succeeded", "stage_seconds": {"asr": 2.0}},
            {"run_id": "2", "status": "succeeded", "stage_seconds": {"asr": 4.0}},
            {"run_id": "3", "status": "timed_out", "stage_seconds": {"asr": 99.0}},
            {"run_id": "4", "status": "failed", "stage_seconds": {}},
        ]
    )
    assert result["attempt_count"] == 4
    assert result["successful_completion_rate"] == 0.5
    assert result["stages"]["asr"]["p50_seconds"] == 3.0
    assert result["stages"]["asr"]["p95_seconds"] == 3.9
    assert result["stages"]["asr"]["successful_measured_denominator"] == 2
    assert result["stages"]["asr"]["failed_attempts_excluded_from_latency"] == 2


def test_stage_latency_requires_unique_runs_and_valid_stage_times():
    import pytest

    with pytest.raises(ValueError, match="identity_status"):
        summarize_stage_runs(
            [
                {"run_id": "same", "status": "succeeded", "stage_seconds": {}},
                {"run_id": "same", "status": "failed", "stage_seconds": {}},
            ]
        )
    with pytest.raises(ValueError, match="duration_invalid"):
        summarize_stage_runs(
            [{"run_id": "1", "status": "succeeded", "stage_seconds": {"asr": -1}}]
        )
