"""Authorizations endpoints; original version-one contracts and guards preserved."""

from uuid import UUID, uuid4
from fastapi import Depends, HTTPException
from services.api.storage import active_scopes, processing_allowed
from services.api.contracts import Identity, AuthorizationInput
from services.domain_contracts import validate_record
from services.api.router_context import ApiServices
from services.api.time_utils import now


def register(app, services: ApiServices):
    database = services.database
    identity = services.identity
    encounter = services.encounter
    audit = services.audit
    profiles = services.profiles

    @app.post("/v1/encounters/{encounter_id}/authorizations", status_code=201)
    def authorize(
        encounter_id: UUID,
        body: AuthorizationInput,
        actor: Identity = Depends(identity),
    ):
        resource, created = str(uuid4()), now()
        with database() as con:
            encounter(con, encounter_id, actor)
            try:
                validate_record(
                    "processing_consent",
                    {
                        "id": resource,
                        "encounter_id": str(encounter_id),
                        **body.model_dump(mode="json"),
                        "granted_at": created,
                    },
                )
            except ValueError:
                raise HTTPException(422, "processing_consent_invalid") from None
            con.execute(
                "INSERT INTO authorizations VALUES (?,?,?,?,NULL)",
                (resource, str(encounter_id), body.model_dump_json(), created),
            )
            audit(con, actor, "authorization_recorded", resource)
        return {"id": resource, "created_at": created, **body.model_dump()}

    @app.post(
        "/v1/encounters/{encounter_id}/authorizations/{authorization_id}/withdraw"
    )
    def withdraw(
        encounter_id: UUID, authorization_id: UUID, actor: Identity = Depends(identity)
    ):
        with database() as con:
            encounter(con, encounter_id, actor)
            row = con.execute(
                "SELECT * FROM authorizations WHERE id=? AND encounter=?",
                (str(authorization_id), str(encounter_id)),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "authorization_not_found")
            withdrawn = row["withdrawn_at"] or now()
            if not row["withdrawn_at"]:
                con.execute(
                    "UPDATE authorizations SET withdrawn_at=? WHERE id=?",
                    (withdrawn, str(authorization_id)),
                )
                audit(con, actor, "authorization_withdrawn", str(authorization_id))
                if not processing_allowed(con, encounter_id):
                    con.execute(
                        """UPDATE jobs SET status='cancelled', error_code='authorization_required',
                        result=NULL, lease_token=NULL, lease_expires_at=NULL, updated_at=?
                        WHERE encounter=? AND status IN ('queued','running')""",
                        (now(), str(encounter_id)),
                    )
        return {"id": str(authorization_id), "withdrawn_at": withdrawn}

    @app.get("/v1/encounters/{encounter_id}/processing-permission")
    def permission(encounter_id: UUID, actor: Identity = Depends(identity)):
        with database() as con:
            encounter(con, encounter_id, actor)
            scopes = active_scopes(con, encounter_id)
            return {
                "recording_authorized": "recording" in scopes,
                "local_processing_authorized": "local_processing" in scopes,
                "external_audio_processing_authorized": False,
                "external_text_processing_authorized": False,
                "inference_enabled": bool(profiles),
            }
