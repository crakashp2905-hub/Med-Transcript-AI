"""Approvals routes with preserved exact-version review contracts."""

from services.audit_integrity import (
    verify as verify_audit,
    approval_body,
    seal_approval,
)
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from services.asr.profiles import canonical_json
from services.review.engine import findings_for
from services.review.models import ApprovalInput


from services.review.service import ReviewService
from services.encounter_state import Stage, advance_persisted
from services.api.contracts import IdempotencyKey
from services.api.idempotency import idempotent


class ApprovalRevocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_note_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def register(app, services: ReviewService):
    database = services.database
    identity = services.identity
    audit = services.audit
    require_processing = services.require_processing
    stamp = services.stamp
    get_tx = services.get_tx
    document = services.document
    current = services.current
    replay = services.replay

    @app.post("/v1/encounters/{eid}/approvals", status_code=201)
    @idempotent(database, replay, "POST:/v1/encounters/{eid}/approvals")
    def approve(
        eid: UUID,
        body: ApprovalInput,
        idempotency_key: IdempotencyKey,
        actor=Depends(identity),
    ):
        with database() as con:
            row = current(con, eid, actor)
            verify_audit(con)
            require_processing(con, eid)
            nr, note = document(con, eid, body.note_version_id)
            if (
                row["current_note"] != nr["id"]
                or body.expected_note_sha256 != nr["sha256"]
            ):
                raise HTTPException(412, "stale_note")
            if (
                row["current_transcript"] != note["transcript_version_id"]
                or str(body.verification_report_id) != note["verification_report_id"]
            ):
                raise HTTPException(412, "stale_inputs_or_verification")
            tr, tx = get_tx(con, eid, row["current_transcript"])
            _, report = document(con, eid, body.verification_report_id, "verification")
            if (
                report["note_sha256"] != nr["sha256"]
                or report["transcript_sha256"] != tr["sha256"]
            ):
                raise HTTPException(412, "stale_verification")
            if report["findings"] or findings_for(note, tx):
                raise HTTPException(409, "blocking_findings")
            existing = con.execute(
                "SELECT * FROM approvals WHERE note=?", (nr["id"],)
            ).fetchone()
            if existing:
                saved = approval_body(con, existing)
                if (
                    saved["clinician_id"] != str(actor.clinician_id)
                    or saved["attestation_version"] != body.attestation_version
                    or saved["verification_report_id"]
                    != str(body.verification_report_id)
                ):
                    raise HTTPException(409, "approval_replay_conflict")
                return saved
            aid, created = str(uuid4()), stamp()
            approved = {
                "id": aid,
                "note_version_id": nr["id"],
                "note_sha256": nr["sha256"],
                "transcript_version_id": tr["id"],
                "transcript_sha256": tr["sha256"],
                "verification_report_id": report["id"],
                "clinician_id": str(actor.clinician_id),
                "approved_at": created,
                "attestation_version": body.attestation_version,
                "patient_identifiers_reconfirmed": True,
            }
            con.execute(
                "INSERT INTO approvals VALUES (?,?,?,?,?)",
                (aid, str(eid), nr["id"], canonical_json(approved), created),
            )
            seal_approval(con, aid, approved, created)
            audit(con, actor, "exact_version_approved", aid)
            advance_persisted(con, eid, Stage.APPROVED)
            return approved

    @app.post("/v1/encounters/{eid}/approvals/{aid}/revoke", status_code=200)
    @idempotent(database, replay, "POST:/v1/encounters/{eid}/approvals/{aid}/revoke")
    def revoke_approval(
        eid: UUID,
        aid: UUID,
        body: ApprovalRevocationInput,
        idempotency_key: IdempotencyKey,
        actor=Depends(identity),
    ):
        with database() as con:
            encounter = current(con, eid, actor)
            verify_audit(con)
            lifecycle = con.execute(
                "SELECT stage FROM encounter_lifecycle WHERE encounter=?",
                (str(eid),),
            ).fetchone()
            if not lifecycle or lifecycle["stage"] != Stage.APPROVED.value:
                raise HTTPException(409, "current_approved_version_required")
            row = con.execute(
                "SELECT * FROM approvals WHERE id=? AND encounter=?",
                (str(aid), str(eid)),
            ).fetchone()
            if not row or encounter["current_note"] != row["note"]:
                raise HTTPException(404, "approval_not_found")
            approved = approval_body(con, row)
            if approved["note_sha256"] != body.expected_note_sha256:
                raise HTTPException(412, "stale_approval")
            audit(con, actor, "exact_version_revoked", str(aid))
            advance_persisted(con, eid, Stage.REVOKED)
            return {
                "approval_id": str(aid),
                "note_version_id": row["note"],
                "status": "revoked",
                "revoked_by": str(actor.clinician_id),
            }
