"""Encounters endpoints; original version-one contracts and guards preserved."""

import json
from uuid import UUID, uuid4
from fastapi import Depends
from services.api.contracts import Identity, IdempotencyKey, EncounterInput
from services.api.router_context import ApiServices
from services.api.time_utils import now


def register(app, services: ApiServices):
    database = services.database
    identity = services.identity
    encounter = services.encounter
    audit = services.audit
    replay = services.replay
    remember = services.remember
    profiles = services.profiles

    @app.get("/health")
    def health():
        with database() as con:
            con.execute("SELECT 1").fetchone()
        return {
            "status": "ok",
            "data_mode": "synthetic_only",
            "inference_enabled": bool(profiles),
        }

    @app.post("/v1/encounters", status_code=201)
    def create_encounter(
        body: EncounterInput,
        idempotency_key: IdempotencyKey,
        actor: Identity = Depends(identity),
    ):
        resource, created = str(uuid4()), now()
        with database() as con:
            scope, fingerprint, previous = replay(
                con,
                actor,
                "create_encounter",
                idempotency_key,
                body.model_dump(mode="json"),
            )
            if previous:
                return previous
            con.execute(
                "INSERT INTO encounters (id,tenant,clinician,body,created_at) VALUES (?,?,?,?,?)",
                (
                    resource,
                    str(actor.tenant_id),
                    str(actor.clinician_id),
                    body.model_dump_json(),
                    created,
                ),
            )
            audit(con, actor, "encounter_created", resource)
            response = {
                "id": resource,
                "created_at": created,
                "status": "awaiting_authorization",
                **body.model_dump(mode="json"),
            }
            remember(con, scope, fingerprint, response)
        return response

    @app.get("/v1/encounters/{encounter_id}")
    def get_encounter(encounter_id: UUID, actor: Identity = Depends(identity)):
        with database() as con:
            row = encounter(con, encounter_id, actor)
            audit(con, actor, "encounter_read", str(encounter_id))
            return {
                "id": row["id"],
                "created_at": row["created_at"],
                **json.loads(row["body"]),
            }
