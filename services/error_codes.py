"""Stable, non-sensitive client errors backed by the shared JSON catalog."""

import json
from enum import StrEnum
from pathlib import Path


class ErrorCode(StrEnum):
    INVALID_MEDIA = "invalid_media"
    AUTHORIZATION_REQUIRED = "authorization_required"
    ASR_FAILED = "asr_failed"
    MODEL_UNAVAILABLE = "model_unavailable"
    INTERNAL = "internal_error"


_CATALOG_PATH = Path(__file__).with_name("error_catalog.json")
with _CATALOG_PATH.open(encoding="utf-8") as _catalog_file:
    ERROR_CATALOG = json.load(_catalog_file)

ERRORS = ERROR_CATALOG["errors"]
FALLBACK_ERROR = ERROR_CATALOG["fallback"]
PUBLIC_MESSAGES = {code: entry["message"] for code, entry in ERRORS.items()}


def public_error(code):
    # Only catalog keys cross the API boundary; arbitrary exception detail may
    # contain PHI, audio metadata, prompts, credentials, or provider responses.
    value = (
        code if isinstance(code, str) and code in ERRORS else ErrorCode.INTERNAL.value
    )
    message = PUBLIC_MESSAGES.get(value, "internal error")
    return {"error_code": value, "message": message}
