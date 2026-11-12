"""Evidence-based gate for adding a second local verifier."""


def decision(primary_errors, secondary_errors, combined_errors):
    for value in (primary_errors, secondary_errors, combined_errors):
        if not isinstance(value, set):
            raise ValueError("error_sets_required")
    distinct = secondary_errors - primary_errors
    improved = len(combined_errors) < len(primary_errors)
    return {
        "distinct_secondary_errors": sorted(distinct),
        "measurable_improvement": improved,
        "include_secondary": improved and bool(distinct),
        "decision": "include" if improved and distinct else "remove_redundant_compute",
    }
