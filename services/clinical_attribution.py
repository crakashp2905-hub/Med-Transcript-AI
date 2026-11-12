"""Conservative attribution/context labels for atomic clinical statements."""

import re


def classify(text):
    lower = text.lower() if isinstance(text, str) else ""
    if not lower.strip():
        assertion = "not_stated"
    elif re.search(
        r"\b(?:not|never)\s+(?:stated|documented|recorded|mentioned|discussed|provided|available)\b|\bno\s+(?:information|mention|documentation|record)\b",
        lower,
    ):
        assertion = "not_stated"
    else:
        assertion = (
            "uncertain"
            if "?" in text
            or re.search(
                r"\b(?:do you|have you|is there|maybe|perhaps|might|possible|not sure)\b",
                lower,
            )
            else "negated"
            if re.search(r"\b(?:denies|no|not)\b", lower)
            else "affirmed"
        )
    subject = (
        "family"
        if re.search(r"\b(?:mother|father|sister|brother|family)\b", lower)
        else "patient"
        if lower
        else "unknown"
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
        "requires_review": assertion in ("uncertain", "not_stated")
        or action == "unknown",
    }
