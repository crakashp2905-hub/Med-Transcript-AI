from services.config_fingerprint import fingerprint


def test_config_fingerprint_is_deterministic_and_redacted():
    result = fingerprint(
        {"mode": "offline", "api_key": "secret-value", "nested": {"token": "abc"}}
    )
    assert len(result["sha256"]) == 64
    assert result["config"]["api_key"] == "[REDACTED]"
    assert result["config"]["nested"]["token"] == "[REDACTED]"
    assert "secret-value" not in str(result)
