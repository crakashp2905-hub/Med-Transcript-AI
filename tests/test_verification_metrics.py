from services.verification_metrics import report


def test_verification_metrics_keep_abstentions_and_failures_separate():
    result = report(
        {"dose": {"tp": 2, "fp": 1, "fn": 0, "tn": 3}},
        abstentions=1,
        timeouts=2,
        malformed=1,
        incomplete=1,
        critical_classes=["dose"],
        safe_classes=["dose"],
        cases_checked=5,
        total_cases=6,
    )
    assert result["classes"]["dose"]["critical_miss_rate"] == 0
    assert result["classes"]["dose"]["safe_case_false_alert_rate"] == 0.25
    assert result["abstentions"] == 1 and result["timeouts"] == 2
    assert result["coverage"] == 5 / 6
    assert result["clinical_sensitivity_claim"] is False


def test_verification_metrics_reject_invalid_counts_and_unknown_policy_classes():
    import pytest

    with pytest.raises(ValueError, match="nonnegative_integers"):
        report({"dose": {"tp": -1, "fp": 0, "fn": 0, "tn": 0}})
    with pytest.raises(ValueError, match="policy_unknown"):
        report(
            {"dose": {"tp": 0, "fp": 0, "fn": 0, "tn": 0}}, critical_classes=["allergy"]
        )
