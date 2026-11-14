"""Fail-closed inferential endpoint validation for paired comparisons."""

import math


def assess_paired_endpoint(
    report, *, expected_endpoint_id, expected_definition_sha256, minimum_pairs
):
    if (
        not isinstance(report, dict)
        or not isinstance(expected_endpoint_id, str)
        or not expected_endpoint_id
        or not isinstance(expected_definition_sha256, str)
        or len(expected_definition_sha256) != 64
        or any(char not in "0123456789abcdef" for char in expected_definition_sha256)
        or type(minimum_pairs) is not int
        or minimum_pairs < 2
    ):
        raise ValueError("statistical_endpoint_policy_invalid")
    reasons = []
    if report.get("endpoint_id") != expected_endpoint_id:
        reasons.append("outcome_definition_drift")
    if report.get("outcome_definition_sha256") != expected_definition_sha256:
        reasons.append("outcome_definition_drift")
    pairs = report.get("paired_consultations")
    if type(pairs) is not int or pairs < minimum_pairs:
        reasons.append("inadequate_paired_sample")
    low, high = (
        report.get("confidence_interval_low"),
        report.get("confidence_interval_high"),
    )
    valid_bounds = (
        isinstance(low, (int, float))
        and not isinstance(low, bool)
        and math.isfinite(low)
        and isinstance(high, (int, float))
        and not isinstance(high, bool)
        and math.isfinite(high)
        and low <= high
    )
    if not valid_bounds:
        reasons.append("confidence_interval_missing_or_invalid")
    elif high >= 0:
        reasons.append("confidence_interval_does_not_exclude_no_improvement")
    return {
        "schema_version": "paired_statistical_endpoint_gate_v1",
        "endpoint_id": expected_endpoint_id,
        "paired_consultations": pairs if type(pairs) is int else None,
        "minimum_paired_consultations": minimum_pairs,
        "outcome_definition_matches": "outcome_definition_drift" not in reasons,
        "confidence_interval_valid": valid_bounds,
        "confidence_interval": [low, high] if valid_bounds else None,
        "status": "fail" if reasons else "pass",
        "reasons": sorted(set(reasons)),
        "clinical_release_authorized": False,
        "interpretation": "statistical_gate_only_not_clinical_approval",
    }
