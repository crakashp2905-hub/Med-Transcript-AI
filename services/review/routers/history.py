"""History routes with preserved exact-version review contracts."""

import json

from services.audit_integrity import verify as verify_audit
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException


from services.review.service import ReviewService
from services.api.idempotency import idempotent
from services.api.contracts import IdempotencyKey


def note_version_metadata(item, approval, current_note_id):
    body = json.loads(item["body"])
    return {
        "id": item["id"], "version": item["version"],
        "sha256": item["sha256"], "created_at": item["created_at"],
        "owner_clinician_id": body.get("creator"),
        "transcript_version_id": body.get("transcript_version_id"),
        "model_lineage": body.get("provenance", {}).get("engine", "unknown"),
        "approval_status": "approved" if approval else body.get("status", "unknown"),
        "approved_at": approval["created_at"] if approval else None,
        "current": item["id"] == current_note_id,
    }


def transcript_version_metadata(item, clinician_id, current_transcript_id):
    body = json.loads(item["body"])
    return {
        "id": item["id"], "version": item["version"],
        "sha256": item["sha256"], "created_at": item["created_at"],
        "owner_clinician_id": str(clinician_id),
        "model_lineage": body.get("provenance", {}).get("engine", "unknown"),
        "current": item["id"] == current_transcript_id,
    }


def register(app, services: ReviewService):
    database = services.database
    identity = services.identity
    encounter = services.encounter
    audit = services.audit
    stamp = services.stamp
    document = services.document
    current = services.current

    def idem(operation):
        return idempotent(database, services.replay, operation)

    @app.get("/v1/encounters/{eid}/versions")
    def versions(eid: UUID, actor=Depends(identity)):
        with database() as con:
            row = current(con, eid, actor)
            notes = []
            for item in con.execute(
                "SELECT id,version,sha256,created_at,body FROM documents "
                "WHERE encounter=? AND kind='note' ORDER BY version DESC LIMIT 100",
                (str(eid),),
            ):
                approval = con.execute(
                    "SELECT created_at FROM approvals WHERE note=?", (item["id"],)
                ).fetchone()
                notes.append(note_version_metadata(item, approval, row["current_note"]))
            transcripts = []
            for item in con.execute(
                "SELECT id,version,sha256,created_at,body FROM transcript_versions "
                "WHERE encounter=? ORDER BY version DESC LIMIT 100",
                (str(eid),),
            ):
                transcripts.append(transcript_version_metadata(
                    item, actor.clinician_id, row["current_transcript"]
                ))
            return {
                "notes": notes,
                "transcripts": transcripts,
                "limit": 100,
            }

    @app.get("/v1/encounters/{eid}/notes/{before}/compare/{after}")
    def compare_notes(eid: UUID, before: UUID, after: UUID, actor=Depends(identity)):
        from services.review.comparison import compare

        with database() as con:
            encounter(con, eid, actor)
            _, a = document(con, eid, before)
            _, b = document(con, eid, after)
            return compare(a, b)

    @app.get("/v1/encounters/{eid}/audit")
    def audit_trail(eid: UUID, actor=Depends(identity)):
        with database() as con:
            verify_audit(con)
            current(con, eid, actor)
            ids = {str(eid)}
            for table in (
                "review_metrics",
                "model_proposals",
                "uploads",
                "jobs",
                "documents",
                "transcript_versions",
                "approvals",
                "exports",
                "authorizations",
            ):
                ids.update(
                    item[0]
                    for item in con.execute(
                        f"SELECT id FROM {table} WHERE encounter=?", (str(eid),)
                    )
                )
            rows = con.execute(
                "SELECT * FROM audit WHERE tenant=? ORDER BY time DESC LIMIT 2000",
                (str(actor.tenant_id),),
            ).fetchall()
            return {
                "items": [dict(item) for item in rows if item["resource"] in ids][:200]
            }

    @app.post("/v1/encounters/{eid}/deletion-requests", status_code=202)
    @idem("encounter-deletion-request")
    def delete_request(
        eid: UUID, idempotency_key: IdempotencyKey, actor=Depends(identity)
    ):
        with database() as con:
            row = current(con, eid, actor)
            if (
                row["legal_hold"]
                or con.execute(
                    "SELECT 1 FROM approvals WHERE encounter=?", (str(eid),)
                ).fetchone()
            ):
                raise HTTPException(409, "record_retention_review_required")
            rid, created = str(uuid4()), stamp()
            con.execute(
                "INSERT INTO deletion_requests VALUES (?,?,?, ?,NULL)",
                (rid, str(eid), "pending", created),
            )
            con.execute(
                "UPDATE encounters SET deleted_at=? WHERE id=?", (created, str(eid))
            )
            con.execute(
                "UPDATE jobs SET status='cancelled',lease_token=NULL,lease_expires_at=NULL WHERE encounter=? AND status IN ('queued','running')",
                (str(eid),),
            )
            audit(con, actor, "encounter_tombstoned", str(eid))
            return {
                "id": rid,
                "status": "pending",
                "backup_expiry": "requires_operator_confirmation",
            }

    @app.get("/v1/deletion-requests/{rid}")
    def deletion_status(rid: UUID, actor=Depends(identity)):
        with database() as con:
            row = con.execute(
                """SELECT deletion_requests.* FROM deletion_requests JOIN encounters
                ON encounters.id=deletion_requests.encounter WHERE deletion_requests.id=?
                AND encounters.tenant=? AND encounters.clinician=?""",
                (str(rid), str(actor.tenant_id), str(actor.clinician_id)),
            ).fetchone()
            if not row:
                raise HTTPException(404, "deletion_request_not_found")
            return {**dict(row), "backup_expiry": "requires_operator_confirmation"}
