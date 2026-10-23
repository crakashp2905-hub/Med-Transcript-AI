"""Synthetic-only encounters and bounded local PCM WAV ingestion."""

import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator

from services.api.ingest import MAX_UPLOAD_BYTES, file_sha256
from services.api.storage import Store, active_scopes, processing_allowed, default_asset_root
from services.asr.profiles import ASRProfile, load_profiles


IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128,
                                      pattern=r"^[a-zA-Z0-9_.-]+$")]


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


class UploadInput(StrictModel):
    bytes: int = Field(gt=0, le=MAX_UPLOAD_BYTES, strict=True)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: Literal["audio/wav"] = "audio/wav"


class TranscriptionInput(StrictModel):
    audio_asset_id: UUID
    inference_profile_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,80}$")


def now():
    return datetime.now(timezone.utc).isoformat()


def create_app(db_path: str, credentials: dict[str, Identity], asset_root: str | None = None,
               asr_profiles: dict[str, ASRProfile] | None = None) -> FastAPI:
    if not credentials or any(len(token) < 32 for token in credentials):
        raise ValueError("Configure service tokens of at least 32 characters")
    # Only digests are retained by the authentication closure.
    identities = {hashlib.sha256(k.encode()).hexdigest(): v for k, v in credentials.items()}
    database = Store(db_path).transaction
    profiles = dict(asr_profiles or {})
    if any(key != profile.profile_id for key, profile in profiles.items()):
        raise ValueError("ASR profile keys must match their profile IDs")
    with database() as con:
        for profile in profiles.values():
            con.execute("INSERT OR IGNORE INTO asr_profiles VALUES (?,?)",
                        (profile.sha256, profile.model_dump_json()))
    assets = Path(asset_root or default_asset_root(db_path))
    assets.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Med Transcript AI — synthetic foundation", version="0.3.0")
    bearer = HTTPBearer(auto_error=False)

    @app.middleware("http")
    async def response_headers(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
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

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={
            "code": "storage_unavailable", "request_id": request.state.request_id},
            headers={"Retry-After": "2"})

    if db_path.startswith(("postgresql://", "postgres://")):
        import psycopg
        app.add_exception_handler(psycopg.OperationalError, database_error)

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
        if row is None or row["deleted_at"]:
            raise HTTPException(404, "encounter_not_found")
        return row

    def audit(con, actor, action, resource):
        con.execute("INSERT INTO audit VALUES (?,?,?,?,?,?)", (str(uuid4()), str(actor.tenant_id),
                    str(actor.clinician_id), action, resource, now()))

    def replay(con, actor, operation, key, body):
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"),
                                                 ensure_ascii=False).encode()).hexdigest()
        scope = (str(actor.tenant_id), str(actor.clinician_id), operation, key_hash)
        row = con.execute("SELECT * FROM idempotency WHERE tenant=? AND actor=? AND operation=? AND key_hash=?",
                          scope).fetchone()
        if row and datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            con.execute("DELETE FROM idempotency WHERE tenant=? AND actor=? AND operation=? AND key_hash=?", scope)
            row = None
        if row and row["fingerprint"] != fingerprint:
            raise HTTPException(409, "idempotency_conflict")
        return scope, fingerprint, json.loads(row["response"]) if row else None

    def remember(con, scope, fingerprint, response):
        con.execute("INSERT INTO idempotency VALUES (?,?,?,?,?,?,?)", (*scope, fingerprint,
                    json.dumps(response), (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()))

    def require_processing(con, encounter_id):
        if not processing_allowed(con, encounter_id):
            raise HTTPException(403, "authorization_required")

    def upload_row(con, encounter_id, upload_id, actor):
        encounter(con, encounter_id, actor)
        row = con.execute("SELECT * FROM uploads WHERE id=? AND encounter=?",
                          (str(upload_id), str(encounter_id))).fetchone()
        if row is None:
            raise HTTPException(404, "upload_not_found")
        return row

    def require_live_upload(row):
        if datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            raise HTTPException(409, "upload_expired")

    @app.get("/health")
    def health():
        return {"status": "ok", "data_mode": "synthetic_only", "inference_enabled": bool(profiles)}

    @app.post("/v1/encounters", status_code=201)
    def create_encounter(body: EncounterInput, idempotency_key: IdempotencyKey,
                         actor: Identity = Depends(identity)):
        resource, created = str(uuid4()), now()
        with database() as con:
            scope, fingerprint, previous = replay(con, actor, "create_encounter", idempotency_key,
                                                   body.model_dump(mode="json"))
            if previous:
                return previous
            con.execute("INSERT INTO encounters (id,tenant,clinician,body,created_at) VALUES (?,?,?,?,?)", (resource, str(actor.tenant_id),
                        str(actor.clinician_id), body.model_dump_json(), created))
            audit(con, actor, "encounter_created", resource)
            response = {"id": resource, "created_at": created, "status": "awaiting_authorization",
                        **body.model_dump(mode="json")}
            remember(con, scope, fingerprint, response)
        return response

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
                if not processing_allowed(con, encounter_id):
                    con.execute("""UPDATE jobs SET status='cancelled', error_code='authorization_required',
                        result=NULL, lease_token=NULL, lease_expires_at=NULL, updated_at=?
                        WHERE encounter=? AND status IN ('queued','running')""", (now(), str(encounter_id)))
        return {"id": str(authorization_id), "withdrawn_at": withdrawn}

    @app.get("/v1/encounters/{encounter_id}/processing-permission")
    def permission(encounter_id: UUID, actor: Identity = Depends(identity)):
        with database() as con:
            encounter(con, encounter_id, actor)
            scopes = active_scopes(con, encounter_id)
            return {"recording_authorized": "recording" in scopes,
                    "local_processing_authorized": "local_processing" in scopes,
                    "external_audio_processing_authorized": False,
                    "external_text_processing_authorized": False,
                    "inference_enabled": bool(profiles)}

    @app.post("/v1/encounters/{encounter_id}/audio-uploads", status_code=201)
    def create_upload(encounter_id: UUID, body: UploadInput, idempotency_key: IdempotencyKey,
                      actor: Identity = Depends(identity)):
        resource, created = str(uuid4()), now()
        expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        with database() as con:
            encounter(con, encounter_id, actor)
            require_processing(con, encounter_id)
            scope, fingerprint, previous = replay(con, actor, f"upload:{encounter_id}", idempotency_key,
                                                   body.model_dump(mode="json"))
            if previous:
                return previous
            con.execute("INSERT INTO uploads VALUES (?,?,?,?,?,?,?)", (resource, str(encounter_id),
                        body.bytes, body.sha256, "open", created, expires))
            response = {"id": resource, "status": "open", "expires_at": expires,
                        "content_url": f"/v1/encounters/{encounter_id}/audio-uploads/{resource}/content"}
            remember(con, scope, fingerprint, response)
            audit(con, actor, "upload_created", resource)
        return response

    @app.get("/v1/encounters/{encounter_id}/audio-uploads/{upload_id}")
    def get_upload(encounter_id: UUID, upload_id: UUID, actor: Identity = Depends(identity)):
        with database() as con:
            row = upload_row(con, encounter_id, upload_id, actor)
            audit(con, actor, "upload_read", str(upload_id))
            return {"id": row["id"], "status": row["status"], "expected_bytes": row["expected_bytes"],
                    "expires_at": row["expires_at"],
                    "expired": datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc)}

    @app.put("/v1/encounters/{encounter_id}/audio-uploads/{upload_id}/content")
    async def upload_content(encounter_id: UUID, upload_id: UUID, request: Request,
                             actor: Identity = Depends(identity)):
        with database() as con:
            row = upload_row(con, encounter_id, upload_id, actor)
            require_processing(con, encounter_id)
            require_live_upload(row)
            if row["status"] != "open":
                raise HTTPException(409, "upload_not_open")
            if request.headers.get("content-type", "").split(";")[0].strip().lower() != "audio/wav":
                raise HTTPException(415, "unsupported_media")
            con.execute("UPDATE uploads SET status='uploading' WHERE id=?", (str(upload_id),))

        temporary = assets / f"{upload_id}.{uuid4()}.part"
        destination = assets / f"{upload_id}.wav"
        digest, received = hashlib.sha256(), 0
        published = False
        try:
            with temporary.open("xb") as target:
                async for chunk in request.stream():
                    received += len(chunk)
                    if received > row["expected_bytes"]:
                        raise HTTPException(413, "upload_size_exceeded")
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            if received != row["expected_bytes"] or digest.hexdigest() != row["expected_sha256"]:
                raise HTTPException(422, "upload_integrity_failure")
            with database() as con:
                current = upload_row(con, encounter_id, upload_id, actor)
                require_live_upload(current)
                require_processing(con, encounter_id)
                os.replace(temporary, destination)
                con.execute("UPDATE uploads SET status='uploaded' WHERE id=?", (str(upload_id),))
                audit(con, actor, "upload_received", str(upload_id))
            published = True
        except OSError:
            raise HTTPException(503, "asset_storage_unavailable") from None
        finally:
            temporary.unlink(missing_ok=True)
            if not published:
                with database() as con:
                    destination.unlink(missing_ok=True)
                    con.execute("UPDATE uploads SET status='open' WHERE id=? AND status='uploading'", (str(upload_id),))
        return {"id": str(upload_id), "status": "uploaded", "bytes": received, "sha256": digest.hexdigest()}

    @app.post("/v1/encounters/{encounter_id}/audio-uploads/{upload_id}/complete", status_code=202)
    def complete_upload(encounter_id: UUID, upload_id: UUID, actor: Identity = Depends(identity)):
        with database() as con:
            row = upload_row(con, encounter_id, upload_id, actor)
            require_processing(con, encounter_id)
            existing = con.execute("SELECT id FROM jobs WHERE upload=? AND stage='audio_ingest'", (str(upload_id),)).fetchone()
            if existing:
                return {"job_id": existing["id"], "status_url": f"/v1/jobs/{existing['id']}"}
            require_live_upload(row)
            if row["status"] != "uploaded":
                raise HTTPException(409, "upload_not_received")
            try:
                source = assets / f"{upload_id}.wav"
                if source.stat().st_size != row["expected_bytes"] or file_sha256(source) != row["expected_sha256"]:
                    raise HTTPException(422, "upload_integrity_failure")
            except OSError:
                raise HTTPException(503, "asset_storage_unavailable") from None
            job_id, created = str(uuid4()), now()
            con.execute("""INSERT INTO jobs (id, upload, encounter, status, created_at, updated_at)
                VALUES (?,?,?,'queued',?,?)""", (job_id, str(upload_id), str(encounter_id), created, created))
            con.execute("UPDATE uploads SET status='complete' WHERE id=?", (str(upload_id),))
            audit(con, actor, "ingest_queued", job_id)
        return {"job_id": job_id, "status_url": f"/v1/jobs/{job_id}"}

    @app.get("/v1/jobs/{job_id}")
    def get_job(job_id: UUID, actor: Identity = Depends(identity)):
        with database() as con:
            row = con.execute("""SELECT jobs.* FROM jobs JOIN encounters ON encounters.id=jobs.encounter
                WHERE jobs.id=? AND encounters.tenant=? AND encounters.clinician=?""",
                (str(job_id), str(actor.tenant_id), str(actor.clinician_id))).fetchone()
            if row is None:
                raise HTTPException(404, "job_not_found")
            audit(con, actor, "job_read", str(job_id))
            return {"id": row["id"], "encounter_id": row["encounter"], "stage": row["stage"],
                    "profile_sha256": row["profile_sha256"],
                    "status": row["status"], "attempts": row["attempts"], "error_code": row["error_code"],
                    "retryable": False, "created_at": row["created_at"], "updated_at": row["updated_at"],
                    "result": json.loads(row["result"]) if row["result"] else None}

    @app.post("/v1/encounters/{encounter_id}/transcriptions", status_code=202)
    def create_transcription(encounter_id: UUID, body: TranscriptionInput, idempotency_key: IdempotencyKey,
                              actor: Identity = Depends(identity)):
        with database() as con:
            encounter(con, encounter_id, actor)
            require_processing(con, encounter_id)
            scope, fingerprint, previous = replay(con, actor, f"transcription:{encounter_id}",
                                                   idempotency_key, body.model_dump(mode="json"))
            if previous:
                return previous
            profile = profiles.get(body.inference_profile_id)
            if profile is None:
                raise HTTPException(503, "asr_profile_unavailable")
            upload = upload_row(con, encounter_id, body.audio_asset_id, actor)
            ingest = con.execute("SELECT * FROM jobs WHERE upload=? AND stage='audio_ingest'",
                                 (upload["id"],)).fetchone()
            if ingest is None or ingest["status"] != "succeeded":
                raise HTTPException(409, "audio_ingest_required")
            metadata = json.loads(ingest["result"])
            if metadata["sample_rate"] != 16000 or metadata["channels"] != 1:
                raise HTTPException(422, "unsupported_asr_input")
            existing = con.execute("SELECT id FROM jobs WHERE upload=? AND stage='transcription' AND profile_sha256=?",
                                   (upload["id"], profile.sha256)).fetchone()
            job_id, created = existing["id"] if existing else str(uuid4()), now()
            if not existing:
                con.execute("""INSERT INTO jobs (id,upload,encounter,status,created_at,updated_at,stage,profile_sha256)
                    VALUES (?,?,?,'queued',?,?,'transcription',?)""",
                    (job_id, upload["id"], str(encounter_id), created, created, profile.sha256))
                audit(con, actor, "transcription_queued", job_id)
            response = {"job_id": job_id, "status_url": f"/v1/jobs/{job_id}"}
            remember(con, scope, fingerprint, response)
        return response

    @app.get("/v1/encounters/{encounter_id}/transcripts/{version}")
    def get_transcript(encounter_id: UUID, version: UUID, actor: Identity = Depends(identity)):
        with database() as con:
            encounter(con, encounter_id, actor)
            row = con.execute("SELECT * FROM transcript_versions WHERE id=? AND encounter=?",
                              (str(version), str(encounter_id))).fetchone()
            if row is None:
                raise HTTPException(404, "transcript_not_found")
            audit(con, actor, "transcript_read", str(version))
            return JSONResponse(content={**json.loads(row["body"]), "sha256": row["sha256"]},
                                headers={"ETag": f'"{row["sha256"]}"'})

    from services.review.routes import register_review_routes
    register_review_routes(app, database, identity, encounter, audit, require_processing, assets, profiles)
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    frontend = Path(__file__).resolve().parents[2] / "apps" / "clinician-web" / "dist"
    if frontend.is_dir():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="web-assets")
        @app.get("/", include_in_schema=False)
        def clinician_web():
            return FileResponse(frontend / "index.html")
    return app


def app_from_env():
    """Uvicorn factory; credentials are provisioned by operator, never by clients."""
    raw = os.environ.get("MED_TRANSCRIPT_IDENTITIES")
    if not raw:
        raise RuntimeError("MED_TRANSCRIPT_IDENTITIES must contain a token-to-identity JSON object")
    identities = {token: Identity.model_validate(value) for token, value in json.loads(raw).items()}
    profile_path = os.environ.get("MED_TRANSCRIPT_ASR_PROFILES")
    return create_app(os.environ.get("MED_TRANSCRIPT_DB", "data/development.sqlite3"), identities,
                      os.environ.get("MED_TRANSCRIPT_ASSETS"), load_profiles(profile_path) if profile_path else None)
