"""Per-class verifier metrics with abstention and failure accounting."""


def report(classes, *, abstentions=0, timeouts=0, malformed=0, incomplete=0):
    if not isinstance(classes, dict) or any(
        not isinstance(value, dict) for value in classes.values()
    ):
        raise ValueError("class_metrics_required")
    for value in classes.values():
        if any(key not in value for key in ("tp", "fp", "fn", "tn")):
            raise ValueError("confusion_counts_required")
    return {
        "classes": classes,
        "abstentions": abstentions,
        "timeouts": timeouts,
        "malformed_outputs": malformed,
        "incomplete_checking": incomplete,
        "clinical_sensitivity_claim": False,
    }
