"""Amendments routes with preserved exact-version review contracts."""
from services.audit_integrity import approval_body
from uuid import UUID

from fastapi import Depends, HTTPException

from services.review.engine import propose_facts
from services.review.models import AmendmentInput


from services.review.service import ReviewService

def register(app, services: ReviewService):
    database = services.database
    identity = services.identity
    require_processing = services.require_processing
    get_tx = services.get_tx
    document = services.document
    current = services.current
    save_note = services.save_note

    @app.post("/v1/encounters/{eid}/amendments", status_code=201)
    def amend(eid: UUID, body: AmendmentInput, actor=Depends(identity)):
        from services.review.models import Fact
        with database() as con:
            row = current(con, eid, actor)
            require_processing(con, eid)
            ar = con.execute("SELECT * FROM approvals WHERE id=? AND encounter=?", (str(body.approval_id), str(eid))).fetchone()
            if not ar:
                raise HTTPException(404, "approval_not_found")
            approval_body(con, ar)
            if row["current_note"] != ar["note"]:
                raise HTTPException(412, "amend_current_approved_version_only")
            _, old = document(con, eid, ar["note"])
            tr, tx = get_tx(con, eid, row["current_transcript"])
            if tr["id"] != old["transcript_version_id"]:
                # Fresh evidence must be selected against the corrected transcript.
                values = [Fact.model_validate(item) for item in propose_facts(tx)]
            else:
                values = [Fact.model_validate({key: value[key] for key in Fact.model_fields if key in value}) for value in old["facts"]]
            return save_note(con, eid, tr, tx, values, actor, old["id"], body.reason)
