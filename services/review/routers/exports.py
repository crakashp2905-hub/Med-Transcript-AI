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
from services.evidence_graph import validate_approved_export
from services.api.contracts import IdempotencyKey
from services.api.idempotency import idempotent


def register(app, services: ReviewService):
    database = services.database
    identity = services.identity
    audit = services.audit
    stamp = services.stamp
    document = services.document
    get_tx = services.get_tx
    current = services.current
    replay = services.replay

    @app.post("/v1/encounters/{eid}/exports", status_code=201)
    @idempotent(database, replay, "POST:/v1/encounters/{eid}/exports")
    def export(
        eid: UUID,
        body: ExportInput,
        idempotency_key: IdempotencyKey,
        actor=Depends(identity),
    ):
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
                if (
                    hashlib.sha256(existing["artifact"].encode("utf-8")).hexdigest()
                    != existing["sha256"]
                ):
                    raise HTTPException(409, "approved_artifact_integrity_failure")
                try:
                    graph = validate_approved_export(
                        transcript=tx,
                        transcript_sha256=tr["sha256"],
                        note=note,
                        note_sha256=nr["sha256"],
                        approval=approval,
                        export_id=existing["id"],
                        artifact_sha256=existing["sha256"],
                    )
                except ValueError:
                    raise HTTPException(
                        409, "approved_artifact_integrity_failure"
                    ) from None
                return {
                    "id": existing["id"],
                    "sha256": existing["sha256"],
                    "evidence_graph_sha256": graph["graph_sha256"],
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
            xid = str(uuid4())
            artifact = render_export(note, approval, body.format, source)
            digest = hashlib.sha256(artifact.encode("utf-8")).hexdigest()
            try:
                graph = validate_approved_export(
                    transcript=tx,
                    transcript_sha256=tr["sha256"],
                    note=note,
                    note_sha256=nr["sha256"],
                    approval=approval,
                    export_id=xid,
                    artifact_sha256=digest,
                )
            except ValueError:
                raise HTTPException(
                    409, "approved_artifact_integrity_failure"
                ) from None
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
                "evidence_graph_sha256": graph["graph_sha256"],
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
            try:
                nr, note = document(con, eid, sealed["note"])
                tr, tx = get_tx(con, eid, note["transcript_version_id"])
                graph = validate_approved_export(
                    transcript=tx,
                    transcript_sha256=tr["sha256"],
                    note=note,
                    note_sha256=nr["sha256"],
                    approval=approval_body(con, sealed),
                    export_id=row["id"],
                    artifact_sha256=row["sha256"],
                )
            except (ValueError, KeyError):
                raise HTTPException(
                    409, "approved_artifact_integrity_failure"
                ) from None
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
                    "X-Evidence-Graph-SHA256": graph["graph_sha256"],
                },
            )
