import pytest

from services.statistical_acceptance import assess_paired_endpoint


HASH = "a" * 64


def _report(**overrides):
    return {
        "endpoint_id": "critical_miss_delta_v1",
        "outcome_definition_sha256": HASH,
        "paired_consultations": 24,
        "confidence_interval_low": -0.12,
        "confidence_interval_high": -0.01,
    } | overrides


def test_statistical_endpoint_requires_sample_ci_and_frozen_definition():
    assert (
        assess_paired_endpoint(
            _report(),
            expected_endpoint_id="critical_miss_delta_v1",
            expected_definition_sha256=HASH,
            minimum_pairs=20,
        )["status"]
        == "pass"
    )
    inadequate = assess_paired_endpoint(
        _report(paired_consultations=12),
        expected_endpoint_id="critical_miss_delta_v1",
        expected_definition_sha256=HASH,
        minimum_pairs=20,
    )
    assert "inadequate_paired_sample" in inadequate["reasons"]
    missing = assess_paired_endpoint(
        _report(confidence_interval_high=None),
        expected_endpoint_id="critical_miss_delta_v1",
        expected_definition_sha256=HASH,
        minimum_pairs=20,
    )
    assert "confidence_interval_missing_or_invalid" in missing["reasons"]
    drift = assess_paired_endpoint(
        _report(outcome_definition_sha256="b" * 64),
        expected_endpoint_id="critical_miss_delta_v1",
        expected_definition_sha256=HASH,
        minimum_pairs=20,
    )
    assert "outcome_definition_drift" in drift["reasons"]


def test_statistical_endpoint_requires_interval_excluding_no_improvement():
    result = assess_paired_endpoint(
        _report(confidence_interval_high=0.01),
        expected_endpoint_id="critical_miss_delta_v1",
        expected_definition_sha256=HASH,
        minimum_pairs=20,
    )
    assert result["status"] == "fail"
    assert "confidence_interval_does_not_exclude_no_improvement" in result["reasons"]
    assert result["clinical_release_authorized"] is False


def test_statistical_endpoint_rejects_invalid_gate_policy():
    with pytest.raises(ValueError, match="policy_invalid"):
        assess_paired_endpoint(
            _report(),
            expected_endpoint_id="",
            expected_definition_sha256=HASH,
            minimum_pairs=20,
        )
