"""Transcripts endpoints; original version-one contracts and guards preserved."""

from uuid import UUID
from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from services.api.contracts import Identity
from services.api.router_context import ApiServices

from services.api.record_integrity import decode_record


def register(app, services: ApiServices):
    database = services.database
    identity = services.identity
    encounter = services.encounter
    audit = services.audit

    @app.get("/v1/encounters/{encounter_id}/transcripts/{version}")
    def get_transcript(
        encounter_id: UUID, version: UUID, actor: Identity = Depends(identity)
    ):
        with database() as con:
            encounter(con, encounter_id, actor)
            row = con.execute(
                "SELECT * FROM transcript_versions WHERE id=? AND encounter=?",
                (str(version), str(encounter_id)),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "transcript_not_found")
            audit(con, actor, "transcript_read", str(version))
            return JSONResponse(
                content={**decode_record(row, "transcript"), "sha256": row["sha256"]},
                headers={"ETag": f'"{row["sha256"]}"'},
            )
