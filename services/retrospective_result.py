"""Reproducible developer-authored retrospective result envelope."""


def report(*, cases, rule_misses_before, rule_misses_after, false_alarms):
    if cases != 52:
        raise ValueError("expected_52_cases")
    if any(
        value < 0 for value in (rule_misses_before, rule_misses_after, false_alarms)
    ):
        raise ValueError("counts_must_be_nonnegative")
    return {
        "cases": cases,
        "rule_misses_before": rule_misses_before,
        "rule_misses_after": rule_misses_after,
        "false_alarms": false_alarms,
        "clinical_sensitivity_claim": False,
    }
