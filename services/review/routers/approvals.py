"""Approvals routes with preserved exact-version review contracts."""

from services.audit_integrity import (
    verify as verify_audit,
    approval_body,
    seal_approval,
)
import json
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException

from services.asr.profiles import canonical_json
from services.review.engine import findings_for
from services.review.models import ApprovalInput


from services.review.service import ReviewService


def register(app, services: ReviewService):
    database = services.database
    identity = services.identity
    audit = services.audit
    require_processing = services.require_processing
    stamp = services.stamp
    get_tx = services.get_tx
    document = services.document
    current = services.current

    @app.post("/v1/encounters/{eid}/approvals", status_code=201)
    def approve(eid: UUID, body: ApprovalInput, actor=Depends(identity)):
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
                return approval_body(con, existing)
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
            return approved
