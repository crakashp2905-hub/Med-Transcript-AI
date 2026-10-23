"""Synthetic-only foundation. No media ingestion or inference is enabled."""

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Identity(StrictModel):
    tenant_id: UUID
    clinician_id: UUID


class EncounterInput(StrictModel):
    patient_reference_id: UUID
    patient_identifiers_confirmed: Literal[True]
    language: Literal["en"] = "en"
    timezone: str = Field(default="Asia/Kolkata", max_length=80)
    workflow: Literal["outpatient_general_medicine"] = "outpatient_general_medicine"
    requested_inference_mode: Literal["fully_local"] = "fully_local"
    synthetic_data: Literal[True]

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown IANA timezone") from None
        return value


class AuthorizationInput(StrictModel):
    scopes: list[Literal["recording", "local_processing"]] = Field(min_length=1, max_length=2)
    policy_version: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    method: Literal["written", "verbal_documented"]
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def future_expiry(cls, value):
        if value.tzinfo is None or value <= datetime.now(timezone.utc):
            raise ValueError("Expiry must be timezone-aware and in the future")
        return value


def now():
    return datetime.now(timezone.utc).isoformat()


def create_app(db_path: str, credentials: dict[str, Identity]) -> FastAPI:
    if not credentials or any(len(token) < 32 for token in credentials):
        raise ValueError("Configure service tokens of at least 32 characters")
    # Only digests are retained by the authentication closure.
    identities = {hashlib.sha256(k.encode()).hexdigest(): v for k, v in credentials.items()}
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def database():
        con = sqlite3.connect(db_path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    with database() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS encounters (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, clinician TEXT NOT NULL,
            body TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS authorizations (
            id TEXT PRIMARY KEY, encounter TEXT NOT NULL REFERENCES encounters(id),
            body TEXT NOT NULL, created_at TEXT NOT NULL, withdrawn_at TEXT);
        CREATE TABLE IF NOT EXISTS audit (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, actor TEXT NOT NULL,
            action TEXT NOT NULL, resource TEXT NOT NULL, time TEXT NOT NULL);
        """)

    app = FastAPI(title="Med Transcript AI — synthetic foundation", version="0.1.0")
    bearer = HTTPBearer(auto_error=False)

    @app.middleware("http")
    async def response_headers(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Default validation responses can echo sensitive submitted values.
        return JSONResponse(status_code=422, content={
            "code": "invalid_request", "request_id": request.state.request_id,
            "guidance": "Check the request against the OpenAPI schema."})

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={
            "code": exc.detail, "request_id": request.state.request_id}, headers=exc.headers)

    def identity(auth: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if auth:
            digest = hashlib.sha256(auth.credentials.encode()).hexdigest()
            for candidate, principal in identities.items():
                if secrets.compare_digest(digest, candidate):
                    return principal
        raise HTTPException(401, "authentication_required", headers={"WWW-Authenticate": "Bearer"})

    def encounter(con, encounter_id, actor):
        row = con.execute("SELECT * FROM encounters WHERE id=? AND tenant=? AND clinician=?",
                          (str(encounter_id), str(actor.tenant_id), str(actor.clinician_id))).fetchone()
        if row is None:
            raise HTTPException(404, "encounter_not_found")
        return row

    def audit(con, actor, action, resource):
        con.execute("INSERT INTO audit VALUES (?,?,?,?,?,?)", (str(uuid4()), str(actor.tenant_id),
                    str(actor.clinician_id), action, resource, now()))

    @app.get("/health")
    def health():
        return {"status": "ok", "data_mode": "synthetic_only", "inference_enabled": False}

    @app.post("/v1/encounters", status_code=201)
    def create_encounter(body: EncounterInput, actor: Identity = Depends(identity)):
        resource, created = str(uuid4()), now()
        with database() as con:
            con.execute("INSERT INTO encounters VALUES (?,?,?,?,?)", (resource, str(actor.tenant_id),
                        str(actor.clinician_id), body.model_dump_json(), created))
            audit(con, actor, "encounter_created", resource)
        return {"id": resource, "created_at": created, "status": "awaiting_authorization", **body.model_dump()}

    @app.get("/v1/encounters/{encounter_id}")
    def get_encounter(encounter_id: UUID, actor: Identity = Depends(identity)):
        with database() as con:
            row = encounter(con, encounter_id, actor)
            audit(con, actor, "encounter_read", str(encounter_id))
            return {"id": row["id"], "created_at": row["created_at"], **json.loads(row["body"])}

    @app.post("/v1/encounters/{encounter_id}/authorizations", status_code=201)
    def authorize(encounter_id: UUID, body: AuthorizationInput, actor: Identity = Depends(identity)):
        resource, created = str(uuid4()), now()
        with database() as con:
            encounter(con, encounter_id, actor)
            con.execute("INSERT INTO authorizations VALUES (?,?,?,?,NULL)",
                        (resource, str(encounter_id), body.model_dump_json(), created))
            audit(con, actor, "authorization_recorded", resource)
        return {"id": resource, "created_at": created, **body.model_dump()}

    @app.post("/v1/encounters/{encounter_id}/authorizations/{authorization_id}/withdraw")
    def withdraw(encounter_id: UUID, authorization_id: UUID, actor: Identity = Depends(identity)):
        with database() as con:
            encounter(con, encounter_id, actor)
            row = con.execute("SELECT * FROM authorizations WHERE id=? AND encounter=?",
                              (str(authorization_id), str(encounter_id))).fetchone()
            if row is None:
                raise HTTPException(404, "authorization_not_found")
            withdrawn = row["withdrawn_at"] or now()
            if not row["withdrawn_at"]:
                con.execute("UPDATE authorizations SET withdrawn_at=? WHERE id=?", (withdrawn, str(authorization_id)))
                audit(con, actor, "authorization_withdrawn", str(authorization_id))
        return {"id": str(authorization_id), "withdrawn_at": withdrawn}

    @app.get("/v1/encounters/{encounter_id}/processing-permission")
    def permission(encounter_id: UUID, actor: Identity = Depends(identity)):
        with database() as con:
            encounter(con, encounter_id, actor)
            rows = con.execute("SELECT body FROM authorizations WHERE encounter=? AND withdrawn_at IS NULL",
                               (str(encounter_id),)).fetchall()
            scopes = set()
            for row in rows:
                body = json.loads(row["body"])
                if datetime.fromisoformat(body["expires_at"]) > datetime.now(timezone.utc):
                    scopes.update(body["scopes"])
            return {"recording_authorized": "recording" in scopes,
                    "local_processing_authorized": "local_processing" in scopes,
                    "external_audio_processing_authorized": False,
                    "external_text_processing_authorized": False,
                    "inference_enabled": False}

    return app


def app_from_env():
    """Uvicorn factory; credentials are provisioned by operator, never by clients."""
    raw = os.environ.get("MED_TRANSCRIPT_IDENTITIES")
    if not raw:
        raise RuntimeError("MED_TRANSCRIPT_IDENTITIES must contain a token-to-identity JSON object")
    identities = {token: Identity.model_validate(value) for token, value in json.loads(raw).items()}
    return create_app(os.environ.get("MED_TRANSCRIPT_DB", "data/development.sqlite3"), identities)
