"""Pairwise safety regression gate independent of aggregate WER."""

import math


def compare(baseline, candidate):
    required = (
        "normalized_wer",
        "critical_misses",
        "omissions",
        "false_blocks",
        "unsourced_approved_statements",
        "cross_tenant_leaks",
    )
    if any(key not in baseline or key not in candidate for key in required):
        raise ValueError("incomplete_regression_vector")
    if baseline.get("dataset_id") != candidate.get("dataset_id"):
        raise ValueError("incomparable_regression_dataset")
    for key in required:
        if (
            type(baseline[key]) not in (int, float)
            or not math.isfinite(baseline[key])
            or baseline[key] < 0
            or type(candidate[key]) not in (int, float)
            or not math.isfinite(candidate[key])
            or candidate[key] < 0
        ):
            raise ValueError("invalid_regression_metric")
    safety_regressions = {
        key: candidate[key] - baseline[key]
        for key in ("critical_misses", "omissions", "false_blocks")
        if candidate[key] > baseline[key]
    }
    absolute_safety_findings = {
        key: candidate[key]
        for key in (
            "critical_misses",
            "unsourced_approved_statements",
            "cross_tenant_leaks",
        )
        if candidate[key] > 0
    }
    blockers = sorted(set(safety_regressions) | set(absolute_safety_findings))
    return {
        "dataset_id": baseline["dataset_id"],
        "baseline": baseline,
        "candidate": candidate,
        "wer_improved": candidate["normalized_wer"] < baseline["normalized_wer"],
        "safety_regressions": safety_regressions,
        "absolute_safety_findings": absolute_safety_findings,
        "promotion_blockers": blockers,
        "promotion": "blocked" if blockers else "review_required",
        "real_patient_release_authorized": False,
    }
