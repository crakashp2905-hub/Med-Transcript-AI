"""Preserve hedged, questioned, and missing clinical information."""

import re


def classify(text):
    if not isinstance(text, str) or not text.strip():
        return {'assertion': 'unknown', 'value': None, 'requires_review': True}
    lower = text.lower()
    uncertain = bool(re.search(r'\b(?:maybe|possibly|might|perhaps|uncertain|not sure)\b', lower)) or '?' in text
    return {'assertion': 'uncertain' if uncertain else 'affirmed', 'value': text,
            'requires_review': uncertain}
