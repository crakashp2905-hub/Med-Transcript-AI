from services.log_redaction import sanitize


def test_log_redaction_removes_sensitive_payloads():
    result = sanitize(
        {"stage": "asr", "transcript": "secret words", "api_key": "k", "attempts": 1}
    )
    assert result["stage"] == "asr" and result["attempts"] == 1
    assert result["transcript"] == "[REDACTED]" and result["api_key"] == "[REDACTED]"
