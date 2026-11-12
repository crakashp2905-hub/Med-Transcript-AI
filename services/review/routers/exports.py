"""Exports routes with preserved exact-version review contracts."""

from services.audit_integrity import approval_body
import hashlib
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException
from fastapi.responses import Response

from services.review.engine import render_export, findings_for
from services.review.models import ExportInput


from services.review.service import ReviewService
from services.clinical_limitations import CLINICAL_LIMITATIONS
from services.domain_contracts import validate_record


def register(app, services: ReviewService):
    database = services.database
    identity = services.identity
    audit = services.audit
    stamp = services.stamp
    document = services.document
    get_tx = services.get_tx
    current = services.current

    @app.post("/v1/encounters/{eid}/exports", status_code=201)
    def export(eid: UUID, body: ExportInput, actor=Depends(identity)):
        with database() as con:
            current(con, eid, actor)
            ar = con.execute(
                "SELECT * FROM approvals WHERE id=? AND encounter=?",
                (str(body.approval_id), str(eid)),
            ).fetchone()
            if not ar:
                raise HTTPException(404, "approval_not_found")
            approval = approval_body(con, ar)
            nr, note = document(con, eid, ar["note"])
            if nr["sha256"] != approval["note_sha256"]:
                raise HTTPException(409, "approved_artifact_integrity_failure")
            tr, tx = get_tx(con, eid, note["transcript_version_id"])
            if (
                tr["sha256"] != approval["transcript_sha256"]
                or tr["sha256"] != note["transcript_sha256"]
            ):
                raise HTTPException(409, "approved_artifact_integrity_failure")
            if findings_for(note, tx):
                raise HTTPException(409, "current_safety_review_required")
            existing = con.execute(
                "SELECT * FROM exports WHERE approval=? AND format=?",
                (ar["id"], body.format),
            ).fetchone()
            if existing:
                return {
                    "id": existing["id"],
                    "sha256": existing["sha256"],
                    "download_url": f"/v1/encounters/{eid}/exports/{existing['id']}",
                }
            source = {
                "transcript_version_id": tr["id"],
                "transcript_sha256": tr["sha256"],
                "provenance": tx.get("provenance", {}),
                "independent_clinical_gold": False,
                "ehr_conformance": "untested",
                "limitations": list(CLINICAL_LIMITATIONS),
            }
            artifact = render_export(note, approval, body.format, source)
            digest = hashlib.sha256(artifact.encode("utf-8")).hexdigest()
            xid = str(uuid4())
            created = stamp()
            try:
                validate_record(
                    "export",
                    {
                        "id": xid,
                        "encounter_id": str(eid),
                        "approval_id": ar["id"],
                        "note_version_id": nr["id"],
                        "note_sha256": nr["sha256"],
                        "transcript_version_id": tr["id"],
                        "transcript_sha256": tr["sha256"],
                        "format": body.format,
                        "artifact_sha256": digest,
                        "created_at": created,
                    },
                )
            except ValueError:
                raise HTTPException(422, "export_metadata_invalid") from None
            con.execute(
                "INSERT INTO exports VALUES (?,?,?,?,?,?,?)",
                (xid, str(eid), ar["id"], body.format, artifact, digest, created),
            )
            audit(con, actor, "approved_export_created", xid)
            return {
                "id": xid,
                "sha256": digest,
                "download_url": f"/v1/encounters/{eid}/exports/{xid}",
            }

    @app.get("/v1/encounters/{eid}/exports/{xid}")
    def download(eid: UUID, xid: UUID, actor=Depends(identity)):
        with database() as con:
            current(con, eid, actor)
            row = con.execute(
                "SELECT * FROM exports WHERE id=? AND encounter=?", (str(xid), str(eid))
            ).fetchone()
            if not row:
                raise HTTPException(404, "export_not_found")
            sealed = con.execute(
                "SELECT * FROM approvals WHERE id=? AND encounter=?",
                (row["approval"], str(eid)),
            ).fetchone()
            if sealed is None:
                raise HTTPException(409, "approved_artifact_integrity_failure")
            approval_body(con, sealed)
            if (
                hashlib.sha256(row["artifact"].encode("utf-8")).hexdigest()
                != row["sha256"]
            ):
                raise HTTPException(409, "approved_artifact_integrity_failure")
            audit(con, actor, "approved_export_downloaded", str(xid))
            extension = {
                "markdown": "md",
                "text": "txt",
                "json": "json",
                "fhir": "json",
            }[row["format"]]
            return Response(
                row["artifact"],
                media_type="application/json"
                if extension == "json"
                else "text/plain; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="approved-note-{xid}.{extension}"',
                    "ETag": f'"{row["sha256"]}"',
                },
            )
