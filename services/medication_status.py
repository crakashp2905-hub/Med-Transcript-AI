"""Conservative medication status classification."""

import re


def classify(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("medication_text_required")
    lower = text.lower()
    status = "unknown"
    for pattern, value in (
        (r"\bstopped\b", "stopped"),
        (r"\brestart(?:ed)?\b", "restarted"),
        (r"\breduced\b", "reduced"),
        (r"\b(?:plan|planned|will)\b", "planned"),
        (r"\b(?:previously|used to|historical)\b", "historical"),
    ):
        if re.search(pattern, lower):
            status = value
            break
    return {
        "text": text,
        "status": status,
        "patient_reported": bool(re.search(r"\b(?:patient|i|she|he)\b", lower)),
        "current_prescription_inferred": False,
        "requires_review": status == "unknown",
    }
