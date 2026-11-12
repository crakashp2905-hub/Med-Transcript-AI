"""Keep unrecognized terminology explicitly unmapped."""

KNOWN = frozenset({"warfarin", "metformin", "lisinopril", "amoxicillin"})


def map_term(term):
    if not isinstance(term, str) or not term.strip():
        raise ValueError("term_required")
    normalized = term.strip().lower()
    if normalized in KNOWN:
        return {
            "term": term,
            "status": "mapped",
            "concept": normalized,
            "certainty": "known",
        }
    return {
        "term": term,
        "status": "unmapped",
        "concept": None,
        "certainty": "unknown",
        "requires_review": True,
    }
