"""Conservative attribution/context labels for atomic clinical statements."""

import re


def classify(text):
    lower = text.lower()
    subject = (
        "family"
        if re.search(r"\b(?:mother|father|sister|brother|family)\b", lower)
        else "patient"
    )
    assertion = (
        "questioned"
        if "?" in text or re.search(r"\b(?:do you|have you|is there)\b", lower)
        else "speculation"
        if re.search(r"\b(?:maybe|perhaps|might|possible)\b", lower)
        else "denied"
        if re.search(r"\b(?:denies|no|not)\b", lower)
        else "affirmed"
    )
    action = (
        "planned"
        if re.search(r"\b(?:plan|will|consider|recommend)\b", lower)
        else "completed"
        if re.search(r"\b(?:started|completed|performed|gave)\b", lower)
        else "unknown"
    )
    return {
        "text": text,
        "subject": subject,
        "assertion": assertion,
        "action_status": action,
        "diagnosis_inferred": False,
        "requires_review": assertion in ("questioned", "speculation")
        or action == "unknown",
    }
