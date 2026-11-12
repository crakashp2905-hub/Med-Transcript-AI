"""Deterministic, redacted configuration diagnostics."""

import hashlib
import json

SENSITIVE = ("secret", "token", "password", "api_key", "private_key")


def _redact(value):
    if isinstance(value, dict):
        return {
            k: (
                "[REDACTED]"
                if any(word in k.lower() for word in SENSITIVE)
                else _redact(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def fingerprint(config):
    redacted = _redact(config)
    canonical = json.dumps(
        redacted, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return {
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "config": redacted,
    }
