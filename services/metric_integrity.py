"""Local review-metric seals. Legacy snapshots are not independent observations."""

from fastapi import HTTPException
from services.canonical import content_sha256
from services.strict_json import loads
from services.domain_contracts import validate_record


def seal(con, body, origin="application_write"):
    validate_record("review_metric", body)
    con.execute(
        "INSERT INTO review_metric_integrity VALUES (?,?,?,?)",
        (body["session_id"], body["id"], content_sha256(body), origin),
    )


def initialize(con):
    for row in con.execute("SELECT * FROM review_metrics").fetchall():
        seal(con, loads(row["body"]), "legacy_snapshot_not_external_attestation")


def decode_metric(con, row, eid, sid):
    saved = con.execute(
        "SELECT * FROM review_metric_integrity WHERE session=?", (str(sid),)
    ).fetchone()
    if row is None:
        if saved is not None:
            raise HTTPException(409, "persisted_artifact_integrity_failure")
        return None
    try:
        body = loads(row["body"])
        validate_record("review_metric", body)
        if (
            saved is None
            or saved["metric_id"] != row["id"]
            or saved["sha256"] != content_sha256(body)
            or row["encounter"] != str(eid)
            or row["session"] != str(sid)
            or body["id"] != row["id"]
            or body["session_id"] != str(sid)
        ):
            raise ValueError("review_metric_binding_mismatch")
    except (ValueError, TypeError, KeyError):
        raise HTTPException(409, "persisted_artifact_integrity_failure") from None
    return body
