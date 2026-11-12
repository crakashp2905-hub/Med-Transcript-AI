"""Separate source span coverage from clinical completeness."""


def analyze(spans, *, duration_ms, clinical_fact_ids, covered_fact_ids):
    if duration_ms <= 0:
        raise ValueError("positive_duration_required")
    filler = sum(1 for span in spans if span.get("kind") == "filler")
    covered_ms = sum(max(0, span["end_ms"] - span["start_ms"]) for span in spans)
    missing = sorted(set(clinical_fact_ids) - set(covered_fact_ids))
    return {
        "covered_ms": covered_ms,
        "duration_ms": duration_ms,
        "coverage_fraction": min(covered_ms / duration_ms, 1),
        "irrelevant_filler_spans": filler,
        "clinical_omission_candidates": missing,
        "clinical_completeness_claim": False,
    }
