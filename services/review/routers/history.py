"""History routes with preserved exact-version review contracts."""

import json
import hashlib
from fastapi.responses import Response

from services.audit_integrity import approval_body, verify as verify_audit
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


def redacted_synthetic_audit_bundle(
    *, encounter, transcript, note, verification, approval, exports, audit_events
):
    body = json.loads(encounter["body"])
    if body.get("synthetic_data") is not True:
        raise ValueError("synthetic_encounter_required")
    segments = (transcript or {}).get("segments", [])
    segment_index = {row.get("segment_id"): i + 1 for i, row in enumerate(segments)}
    facts = (note or {}).get("facts", [])
    evidence = []
    for index, fact in enumerate(facts, start=1):
        citation = fact.get("evidence")
        quote = citation.get("quote", "") if isinstance(citation, dict) else ""
        quote = quote if isinstance(quote, str) else ""
        segment_id = citation.get("segment_id") if isinstance(citation, dict) else None
        evidence.append(
            {
                "fact_index": index,
                "source_segment_ordinal": segment_index.get(segment_id),
                "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest()
                if quote
                else None,
                "source_text_included": False,
            }
        )
    findings = (verification or {}).get("findings", [])
    severities = {}
    for finding in findings:
        severity = str(finding.get("severity", "unknown"))
        severities[severity] = severities.get(severity, 0) + 1
    ordered_events = sorted(audit_events, key=lambda row: row["time"], reverse=True)
    return {
        "schema_version": "synthetic_case_audit_bundle_v1",
        "scope": "synthetic_only_redacted_review_metadata",
        "limitations": [
            "Synthetic development evidence; not independent clinical validation.",
            "Audio, patient identifiers, user identifiers, source text and note text are omitted.",
            "Evidence references are ordinal and quote hashes; hashes do not establish truth.",
        ],
        "source": {
            "available": transcript is not None,
            "version": transcript.get("version") if transcript else None,
            "sha256": transcript.get("sha256") if transcript else None,
            "duration_ms": transcript.get("duration_ms") if transcript else None,
            "segment_count": len(segments),
            "untranscribed_interval_count": len(
                transcript.get("untranscribed_intervals", []) if transcript else []
            ),
            "model_or_engine": (transcript or {}).get("provenance", {}).get(
                "profile_id"
            )
            or (transcript or {}).get("provenance", {}).get("engine"),
        },
        "note": {
            "available": note is not None,
            "version": note.get("version") if note else None,
            "sha256": note.get("sha256") if note else None,
            "status": "approved" if approval else "unapproved_or_absent",
            "fact_count": len(facts),
            "evidence_reference_count": sum(bool(f.get("evidence")) for f in facts),
        },
        "evidence_summary": evidence,
        "verification": {
            "available": verification is not None,
            "gate": (verification or {}).get("gate"),
            "finding_count": len(findings),
            "finding_counts_by_severity": severities,
        },
        "approval": {"present": approval is not None},
        "exports": [
            {"format": row["format"], "sha256": row["sha256"]}
            for row in exports
        ],
        "audit_events": [
            {"time": row["time"], "action": row["action"]}
            for row in ordered_events[:200]
        ],
        "audit_event_count": len(ordered_events),
        "audit_events_truncated": len(ordered_events) > 200,
        "redacted": {
            "patient_reference": True,
            "encounter_id": True,
            "tenant_id": True,
            "clinician_id": True,
            "audio": True,
            "transcript_text": True,
            "clinical_note_text": True,
        },
    }


def register(app, services: ReviewService):
    database = services.database
    identity = services.identity
    encounter = services.encounter
    audit = services.audit
    stamp = services.stamp
    document = services.document
    current = services.current
    get_tx = services.get_tx

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

    @app.get("/v1/encounters/{eid}/audit-bundle")
    def audit_bundle(eid: UUID, actor=Depends(identity)):
        with database() as con:
            verify_audit(con)
            row = current(con, eid, actor)
            try:
                source_row, source = (
                    get_tx(con, eid, row["current_transcript"])
                    if row["current_transcript"]
                    else (None, None)
                )
                transcript = {**source, "sha256": source_row["sha256"]} if source else None
                note_row, note = (
                    document(con, eid, row["current_note"])
                    if row["current_note"]
                    else (None, None)
                )
                if note:
                    note = {**note, "sha256": note_row["sha256"]}
                    _, verification = document(
                        con, eid, note["verification_report_id"], "verification"
                    )
                    approval_row = con.execute(
                        "SELECT * FROM approvals WHERE note=?", (note["id"],)
                    ).fetchone()
                    approval = approval_body(con, approval_row) if approval_row else None
                else:
                    verification, approval = None, None
                export_rows = con.execute(
                    "SELECT format,sha256 FROM exports WHERE encounter=? ORDER BY created_at",
                    (str(eid),),
                ).fetchall()
                resource_ids = {str(eid)}
                for table in ("uploads", "jobs", "documents", "transcript_versions", "approvals", "exports", "authorizations", "review_metrics", "model_proposals"):
                    resource_ids.update(r[0] for r in con.execute(f"SELECT id FROM {table} WHERE encounter=?", (str(eid),)))
                matching_events = []
                resources = sorted(resource_ids)
                for offset in range(0, len(resources), 400):
                    chunk = resources[offset : offset + 400]
                    placeholders = ",".join("?" for _ in chunk)
                    matching_events.extend(
                        con.execute(
                            f"SELECT time,action,resource FROM audit WHERE tenant=? AND resource IN ({placeholders})",
                            [str(actor.tenant_id), *chunk],
                        ).fetchall()
                    )
                bundle = redacted_synthetic_audit_bundle(
                    encounter=row,
                    transcript=transcript,
                    note=note,
                    verification=verification,
                    approval=approval,
                    exports=export_rows,
                    audit_events=matching_events,
                )
            except ValueError as exc:
                if str(exc) == "synthetic_encounter_required":
                    raise HTTPException(404, "audit_bundle_not_found") from None
                raise
            audit(con, actor, "synthetic_audit_bundle_downloaded", str(eid))
        return Response(
            content=json.dumps(bundle, indent=2, ensure_ascii=False),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="synthetic-case-audit-bundle.json"'},
        )

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
