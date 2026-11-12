"""Verification routes with preserved exact-version review contracts."""

from uuid import UUID, uuid4

from fastapi import Depends, HTTPException

from services.review.models import ResolutionInput


from services.review.service import ReviewService


def register(app, services: ReviewService):
    database = services.database
    identity = services.identity
    audit = services.audit
    require_processing = services.require_processing
    get_tx = services.get_tx
    document = services.document
    current = services.current
    save_note = services.save_note

    @app.get("/v1/encounters/{eid}/verification")
    def verification(eid: UUID, actor=Depends(identity)):
        with database() as con:
            row = current(con, eid, actor)
            if not row["current_note"]:
                raise HTTPException(409, "note_required")
            _, body = document(con, eid, row["current_note"])
            _, report = document(
                con, eid, body["verification_report_id"], "verification"
            )
            return {
                **report,
                "stale": body["transcript_version_id"] != row["current_transcript"],
            }

    @app.post("/v1/encounters/{eid}/findings/{fid}/resolve", status_code=201)
    def resolve(eid: UUID, fid: UUID, body: ResolutionInput, actor=Depends(identity)):
        from services.review.models import Fact
        from services.review.clinical import extract

        with database() as con:
            row = current(con, eid, actor)
            require_processing(con, eid)
            nr, old = document(con, eid, row["current_note"])
            if nr["sha256"] != body.expected_note_sha256:
                raise HTTPException(412, "stale_note")
            if con.execute(
                "SELECT 1 FROM approvals WHERE note=?", (nr["id"],)
            ).fetchone():
                raise HTTPException(409, "amendment_required")
            _, report = document(
                con, eid, old["verification_report_id"], "verification"
            )
            if not any(
                item["finding_id"] == str(fid) and item["fact_id"] == str(body.fact_id)
                for item in report["findings"]
            ):
                raise HTTPException(404, "finding_not_found")
            if old["transcript_version_id"] != row["current_transcript"]:
                raise HTTPException(412, "stale_transcript")
            values = []
            for value in old["facts"]:
                value = {key: value[key] for key in Fact.model_fields if key in value}
                if value["fact_id"] == str(body.fact_id):
                    if (
                        value["text"] == body.corrected_text
                        and value["origin"] != "source_linked"
                    ):
                        raise HTTPException(422, "clinical_correction_required")
                    # Explicit clinician correction is a new clinician statement,
                    # not a rewritten assertion with an unchanged source citation.
                    if value["origin"] == "source_linked":
                        original = {
                            **value,
                            "text": value["evidence"]["quote"],
                            "excluded": True,
                            "clarification": body.reason,
                            "reviewed": True,
                            "critical_reviewed": True,
                        }
                        values.append(Fact.model_validate(original))
                    proposed = extract(
                        {
                            "segments": [
                                {
                                    "segment_id": str(uuid4()),
                                    "text": body.corrected_text,
                                }
                            ]
                        }
                    )
                    for entry in proposed:
                        entry.update(
                            origin="clinician_entered",
                            evidence=None,
                            clarification=body.reason,
                            reviewed=True,
                            critical_reviewed=True,
                            section=value["section"],
                            clinical_source="clinician_statement",
                        )
                        if entry["subject"] == "unknown":
                            entry["subject"] = value["subject"]
                        if entry["temporality"] == "unknown":
                            entry["temporality"] = value["temporality"]
                        values.append(Fact.model_validate(entry))
                    continue
                values.append(Fact.model_validate(value))
            if len(values) > 300:
                raise HTTPException(422, "too_many_facts_split_review")
            tr, tx = get_tx(con, eid, old["transcript_version_id"])
            result = save_note(
                con, eid, tr, tx, values, actor, nr["id"], old["amendment_reason"]
            )
            audit(con, actor, "finding_corrected_new_version", str(fid))
            return result
