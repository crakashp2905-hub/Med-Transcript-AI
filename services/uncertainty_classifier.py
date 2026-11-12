"""Preserve hedged, questioned, and missing clinical information."""

import re


def classify(text):
    if not isinstance(text, str) or not text.strip():
        return {"assertion": "not_stated", "value": None, "requires_review": True}
    lower = text.lower()
    if re.search(
        r"\b(?:not|never)\s+(?:stated|documented|recorded|mentioned|discussed|provided|available)\b|\bno\s+(?:information|mention|documentation|record)\b",
        lower,
    ):
        return {"assertion": "not_stated", "value": text, "requires_review": True}
    uncertain = (
        bool(
            re.search(r"\b(?:maybe|possibly|might|perhaps|uncertain|not sure)\b", lower)
        )
        or "?" in text
    )
    negated = bool(re.search(r"\b(?:no|not|never|denies|denied|without)\b", lower))
    return {
        "assertion": "uncertain" if uncertain else "negated" if negated else "affirmed",
        "value": text,
        "requires_review": uncertain,
    }
