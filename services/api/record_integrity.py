"""Fail closed on corrupted persisted text before using clinical evidence."""

from fastapi import HTTPException
from pydantic import ValidationError
from services.canonical import content_sha256
from services.domain_contracts import validate_record
from services.strict_json import loads


def decode_record(row, kind):
    try:
        body = loads(row["body"])
        if content_sha256(body) != row["sha256"]:
            raise ValueError("record_digest_mismatch")
        validate_record(kind, body)
        if str(body["id"]) != row["id"]:
            raise ValueError("record_identity_mismatch")
        if kind in ("transcript", "note") and (
            str(body["encounter_id"]) != row["encounter"]
            or body["version"] != row["version"]
        ):
            raise ValueError("record_scope_or_version_mismatch")
    except (ValueError, TypeError, KeyError, ValidationError):
        raise HTTPException(409, "persisted_artifact_integrity_failure") from None
    return body
