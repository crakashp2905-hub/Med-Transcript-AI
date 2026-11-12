"""Opt-in, fixed local terminology hints with no transcript mutation."""

LOCAL_LEXICON = frozenset(
    {"warfarin", "metformin", "lisinopril", "amoxicillin", "paracetamol"}
)


def apply_hints(text, *, enabled=False, lexicon=LOCAL_LEXICON):
    if not isinstance(text, str):
        raise ValueError("text_required")
    if not enabled:
        return {
            "text": text,
            "hints_used": False,
            "matched_terms": [],
            "medication_hallucination_risk": "not_applicable",
        }
    allowed = (
        LOCAL_LEXICON
        if lexicon is LOCAL_LEXICON
        else frozenset(lexicon) & LOCAL_LEXICON
    )
    lower = text.lower()
    matched = sorted(term for term in allowed if term in lower)
    return {
        "text": text,
        "hints_used": True,
        "matched_terms": matched,
        "medication_hallucination_risk": "requires_review",
    }
