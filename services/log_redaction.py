"""Redact sensitive fields before structured logging."""

SENSITIVE = {
    "note_text",
    "transcript",
    "secret",
    "auth_cookie",
    "api_key",
    "audio",
    "prompt",
    "provider_response",
}


def sanitize(event):
    if not isinstance(event, dict):
        raise ValueError("event_required")
    return {
        key: ("[REDACTED]" if key in SENSITIVE else value)
        for key, value in event.items()
    }
