from services.retrospective_result import report


def test_retrospective_52_case_result_is_reproducible_without_sensitivity_claim():
    result = report(
        cases=52, rule_misses_before=13, rule_misses_after=0, false_alarms=4
    )
    assert result["cases"] == 52
    assert result["rule_misses_before"] == 13 and result["rule_misses_after"] == 0
    assert result["false_alarms"] == 4
    assert result["clinical_sensitivity_claim"] is False
