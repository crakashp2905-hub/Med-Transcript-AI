"""Notes routes with preserved exact-version review contracts."""

from uuid import UUID

from fastapi import Depends, Header, HTTPException
from fastapi.responses import JSONResponse

from services.review.models import DraftInput, NoteEdit


from services.review.service import ReviewService


def register(app, services: ReviewService):
    database = services.database
    identity = services.identity
    require_processing = services.require_processing
    get_tx = services.get_tx
    document = services.document
    current = services.current
    if_current = services.if_current
    save_note = services.save_note

    @app.post("/v1/encounters/{eid}/drafts", status_code=201)
    def draft(eid: UUID, body: DraftInput, actor=Depends(identity)):
        with database() as con:
            row = current(con, eid, actor)
            require_processing(con, eid)
            if row["current_transcript"] != str(body.transcript_version_id):
                raise HTTPException(412, "stale_transcript")
            if (
                row["current_note"]
                and con.execute(
                    "SELECT 1 FROM approvals WHERE note=?", (row["current_note"],)
                ).fetchone()
            ):
                raise HTTPException(409, "amendment_required")
            tr, tx = get_tx(con, eid, body.transcript_version_id)
            return save_note(con, eid, tr, tx, body.facts, actor, row["current_note"])

    @app.get("/v1/encounters/{eid}/notes/{nid}")
    def note(eid: UUID, nid: UUID, actor=Depends(identity)):
        with database() as con:
            current(con, eid, actor)
            row, body = document(con, eid, nid)
            return JSONResponse(
                content={**body, "sha256": row["sha256"]},
                headers={"ETag": f'"{row["sha256"]}"'},
            )

    @app.patch("/v1/encounters/{eid}/notes/{nid}", status_code=201)
    def edit_note(
        eid: UUID,
        nid: UUID,
        body: NoteEdit,
        if_match: str = Header(alias="If-Match"),
        actor=Depends(identity),
    ):
        with database() as con:
            row = current(con, eid, actor)
            require_processing(con, eid)
            nr, old = document(con, eid, nid)
            if_current(row, "current_note", nid, nr["sha256"], if_match)
            if con.execute(
                "SELECT 1 FROM approvals WHERE note=?", (str(nid),)
            ).fetchone():
                raise HTTPException(409, "amendment_required")
            if row["current_transcript"] != str(body.transcript_version_id):
                raise HTTPException(412, "stale_transcript")
            tr, tx = get_tx(con, eid, body.transcript_version_id)
            return save_note(
                con,
                eid,
                tr,
                tx,
                body.facts,
                actor,
                str(nid),
                body.amendment_reason or old["amendment_reason"],
            )
