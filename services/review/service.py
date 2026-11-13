"""Shared exact-version review service; scoped dependencies are passed explicitly."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ContextManager
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from services.asr.profiles import ASRProfile, canonical_json, content_sha256
from services.api.record_integrity import decode_record
from services.domain_contracts import validate_record
from services.review.engine import (
    directional_coverage,
    findings_for,
    render_sections,
    validate_evidence,
    RULES_VERSION,
)
from services.encounter_state import Stage, advance_persisted


class ReviewStateError(HTTPException):
    """Typed safe state failure. Details are machine codes, never source content."""

    def __init__(self, status_code: int, detail: str):
        if not detail.replace("_", "").isalnum():
            raise ValueError("invalid_review_error_code")
        super().__init__(status_code, detail)


@dataclass(frozen=True)
class ReviewService:
    database: Callable[[], ContextManager[Any]]
    identity: Callable[..., Any]
    encounter: Callable[..., Any]
    audit: Callable[..., None]
    require_processing: Callable[..., None]
    assets: Path
    profiles: dict[str, ASRProfile]
    replay: Callable[..., Any]

    def stamp(self):
        return datetime.now(timezone.utc).isoformat()

    def get_tx(self, con, eid, tid):
        row = con.execute(
            "SELECT * FROM transcript_versions WHERE encounter=? AND id=?",
            (str(eid), str(tid)),
        ).fetchone()
        if row is None:
            raise ReviewStateError(404, "transcript_not_found")
        return row, decode_record(row, "transcript")

    def document(self, con, eid, did, kind="note"):
        row = con.execute(
            "SELECT * FROM documents WHERE encounter=? AND id=? AND kind=?",
            (str(eid), str(did), kind),
        ).fetchone()
        if row is None:
            raise ReviewStateError(404, "document_not_found")
        body = decode_record(row, kind)
        if kind in ("note", "verification"):
            source_row, source = self.get_tx(con, eid, body["transcript_version_id"])
            if source_row["sha256"] != body["transcript_sha256"]:
                raise ReviewStateError(409, "persisted_artifact_integrity_failure")
            if kind == "note":
                try:
                    validate_evidence(validate_record("note", body).facts, source)
                except HTTPException:
                    raise ReviewStateError(
                        409, "persisted_artifact_integrity_failure"
                    ) from None
            else:
                note = con.execute(
                    "SELECT sha256 FROM documents WHERE id=? AND encounter=? AND kind='note'",
                    (body["note_version_id"], str(eid)),
                ).fetchone()
                if note is None or note["sha256"] != body["note_sha256"]:
                    raise ReviewStateError(409, "persisted_artifact_integrity_failure")
        return row, body

    def current(self, con, eid, actor):
        encounter = self.encounter
        return encounter(con, eid, actor)

    def if_current(self, row, field, resource, sha, etag):
        if row[field] != str(resource) or etag != f'"{sha}"':
            raise ReviewStateError(412, "version_changed_reload_required")

    def store_tx(self, con, eid, upload, body, actor, parent=None):
        audit = self.audit
        stamp = self.stamp
        tid = str(uuid4())
        version = con.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM transcript_versions WHERE encounter=?",
            (str(eid),),
        ).fetchone()[0]
        body.update(
            id=tid,
            version=version,
            encounter_id=str(eid),
            parent_version_id=parent,
            creator=str(actor.clinician_id),
            created_at=stamp(),
        )
        validate_record("transcript", body)
        digest = content_sha256(body)
        con.execute(
            "INSERT INTO transcript_versions VALUES (?,?,?,?,?,?,?,?)",
            (
                tid,
                str(eid),
                upload,
                None,
                version,
                digest,
                canonical_json(body),
                stamp(),
            ),
        )
        con.execute(
            "UPDATE encounters SET current_transcript=? WHERE id=?", (tid, str(eid))
        )
        lifecycle = con.execute(
            "SELECT stage FROM encounter_lifecycle WHERE encounter=?", (str(eid),)
        ).fetchone()
        if lifecycle and lifecycle["stage"] == Stage.CREATED.value:
            advance_persisted(con, eid, Stage.RECORDING)
        advance_persisted(con, eid, Stage.TRANSCRIBED)
        audit(con, actor, "transcript_version_created", tid)
        return {**body, "sha256": digest}

    def save_note(
        self, con, eid, tx_row, tx, facts, actor, parent=None, amendment_reason=""
    ):
        audit = self.audit
        stamp = self.stamp
        if parent is not None:
            parent_row = con.execute(
                "SELECT id FROM documents WHERE id=? AND encounter=? AND kind='note'",
                (str(parent), str(eid)),
            ).fetchone()
            if parent_row is None:
                raise ReviewStateError(409, "amendment_parent_not_found")
        validate_evidence(facts, tx)
        version = con.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM documents WHERE encounter=? AND kind='note'",
            (str(eid),),
        ).fetchone()[0]
        nid, rid, created = str(uuid4()), str(uuid4()), stamp()
        values = [fact.model_dump(mode="json") for fact in facts]
        for value in values:
            value["review_actor"] = (
                str(actor.clinician_id) if value["reviewed"] else None
            )
            value["reviewed_at"] = created if value["reviewed"] else None
        body = {
            "schema_version": "1.0",
            "id": nid,
            "version": version,
            "encounter_id": str(eid),
            "parent_version_id": parent,
            "transcript_version_id": tx_row["id"],
            "transcript_sha256": tx_row["sha256"],
            "facts": values,
            "sections": render_sections(values, tx_row["id"]),
            "verification_report_id": rid,
            "creator": str(actor.clinician_id),
            "created_at": created,
            "amendment_reason": amendment_reason,
            "template_id": "reviewed_facts_soap_v1",
            "status": "review_required",
            "provenance": {"engine": "deterministic_reviewed_facts_template_v1"},
        }
        validate_record("note", body)
        digest = content_sha256(body)
        findings = findings_for(body, tx)
        report = {
            "schema_version": "1.0",
            "id": rid,
            "note_version_id": nid,
            "note_sha256": digest,
            "transcript_version_id": tx_row["id"],
            "transcript_sha256": tx_row["sha256"],
            "validator_version": RULES_VERSION,
            "findings": findings,
            "directional_coverage": directional_coverage(body, tx, findings),
            "gate": "blocked" if findings else "ready",
            "created_at": created,
        }
        validate_record("verification", report)
        con.execute(
            "INSERT INTO documents VALUES (?,?,?,?,?,?,?)",
            (nid, str(eid), "note", version, digest, canonical_json(body), created),
        )
        con.execute(
            "INSERT INTO documents VALUES (?,?,?,?,?,?,?)",
            (
                rid,
                str(eid),
                "verification",
                version,
                content_sha256(report),
                canonical_json(report),
                created,
            ),
        )
        con.execute("UPDATE encounters SET current_note=? WHERE id=?", (nid, str(eid)))
        advance_persisted(con, eid, Stage.DRAFTED)
        advance_persisted(con, eid, Stage.VERIFIED)
        audit(con, actor, "note_version_created", nid)
        return {"note": {**body, "sha256": digest}, "verification": report}
