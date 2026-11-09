"""Stable, non-sensitive client error codes and messages."""

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_MEDIA = 'invalid_media'
    AUTHORIZATION_REQUIRED = 'authorization_required'
    ASR_FAILED = 'asr_failed'
    MODEL_UNAVAILABLE = 'model_unavailable'
    INTERNAL = 'internal_error'


PUBLIC_MESSAGES = {code: code.value.replace('_', ' ') for code in ErrorCode}


def public_error(code):
    try:
        value = ErrorCode(code)
    except ValueError:
        value = ErrorCode.INTERNAL
    return {'error_code': value.value, 'message': PUBLIC_MESSAGES[value]}
