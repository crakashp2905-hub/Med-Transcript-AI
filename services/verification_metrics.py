"""Per-class verifier metrics with abstention and failure accounting."""


def report(
    classes,
    *,
    abstentions=0,
    timeouts=0,
    malformed=0,
    incomplete=0,
    critical_classes=(),
    safe_classes=(),
    cases_checked=None,
    total_cases=None,
):
    if not isinstance(classes, dict) or any(
        not isinstance(value, dict) for value in classes.values()
    ):
        raise ValueError("class_metrics_required")
    if set(critical_classes) - set(classes) or set(safe_classes) - set(classes):
        raise ValueError("verification_class_policy_unknown")
    scored = {}
    for name, value in classes.items():
        if any(key not in value for key in ("tp", "fp", "fn", "tn")):
            raise ValueError("confusion_counts_required")
        counts = {key: value[key] for key in ("tp", "fp", "fn", "tn")}
        if any(type(count) is not int or count < 0 for count in counts.values()):
            raise ValueError("confusion_counts_must_be_nonnegative_integers")
        positive = counts["tp"] + counts["fn"]
        negative = counts["fp"] + counts["tn"]
        scored[name] = {
            **counts,
            "critical_miss_rate": counts["fn"] / positive if positive else None,
            "safe_case_false_alert_rate": counts["fp"] / negative if negative else None,
            "checked_count": sum(counts.values()),
        }
    for value in (abstentions, timeouts, malformed, incomplete):
        if type(value) is not int or value < 0:
            raise ValueError("verification_failure_counts_invalid")
    if total_cases is not None and (type(total_cases) is not int or total_cases < 0):
        raise ValueError("verification_total_cases_invalid")
    if cases_checked is not None and (
        type(cases_checked) is not int or cases_checked < 0
    ):
        raise ValueError("verification_cases_checked_invalid")
    if (
        total_cases is not None
        and cases_checked is not None
        and cases_checked > total_cases
    ):
        raise ValueError("verification_checked_exceeds_total")
    return {
        "classes": scored,
        "critical_classes": sorted(critical_classes),
        "safe_classes": sorted(safe_classes),
        "abstentions": abstentions,
        "timeouts": timeouts,
        "malformed_outputs": malformed,
        "incomplete_checking": incomplete,
        "cases_checked": cases_checked,
        "total_cases": total_cases,
        "coverage": cases_checked / total_cases if total_cases else None,
        "clinical_sensitivity_claim": False,
    }
