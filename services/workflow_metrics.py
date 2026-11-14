"""Simulated workflow quality, cost, and correction metrics."""

import math


def record(
    *,
    critical_misses,
    benign_false_blocks,
    covered,
    total,
    runtime_seconds,
    memory_bytes,
    corrections,
):
    if (
        total < 0
        or covered < 0
        or covered > total
        or any(
            value < 0
            for value in (
                critical_misses,
                benign_false_blocks,
                runtime_seconds,
                memory_bytes,
                corrections,
            )
        )
    ):
        raise ValueError("invalid_workflow_metrics")
    return {
        "critical_misses": critical_misses,
        "benign_false_blocks": benign_false_blocks,
        "coverage": None if total == 0 else covered / total,
        "runtime_seconds": runtime_seconds,
        "memory_bytes": memory_bytes,
        "reviewer_corrections": corrections,
    }


def summarize_stage_runs(runs):
    """Report completion rates and stage p50/p95 with explicit denominators.

    Only successful attempts with a measured stage duration contribute to that
    stage's latency quantiles. Failures and incomplete measurements stay counted.
    """
    if not isinstance(runs, list) or not runs:
        raise ValueError("workflow_runs_required")
    valid_statuses = {"succeeded", "failed", "timed_out", "aborted"}
    seen = set()
    stages = {}
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("workflow_run_invalid")
        run_id = run.get("run_id")
        status = run.get("status")
        durations = run.get("stage_seconds")
        if (
            not isinstance(run_id, str)
            or not run_id
            or run_id in seen
            or status not in valid_statuses
            or not isinstance(durations, dict)
        ):
            raise ValueError("workflow_run_identity_status_or_stages_invalid")
        seen.add(run_id)
        for stage, duration in durations.items():
            if (
                not isinstance(stage, str)
                or not stage
                or not isinstance(duration, (int, float))
                or isinstance(duration, bool)
                or not math.isfinite(duration)
                or duration < 0
            ):
                raise ValueError("workflow_stage_duration_invalid")
            stages.setdefault(stage, [])
            if status == "succeeded":
                stages[stage].append(duration)
    successes = sum(run["status"] == "succeeded" for run in runs)
    status_counts = {
        status: sum(run["status"] == status for run in runs)
        for status in sorted(valid_statuses)
    }
    return {
        "schema_version": "workflow_stage_metrics_v1",
        "attempt_count": len(runs),
        "status_counts": status_counts,
        "successful_completion_count": successes,
        "successful_completion_rate": successes / len(runs),
        "stage_latency_policy": "successful_runs_with_stage_measurement_only",
        "stages": {
            stage: {
                "p50_seconds": _linear_quantile(values, 0.50),
                "p95_seconds": _linear_quantile(values, 0.95),
                "successful_measured_denominator": len(values),
                "failed_attempts_excluded_from_latency": len(runs) - successes,
                "successful_attempts_missing_measurement": successes - len(values),
            }
            for stage, values in sorted(stages.items())
        },
    }


def _linear_quantile(values, probability):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction
