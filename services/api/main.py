"""Synthetic-only encounters and bounded local PCM WAV ingestion."""

from services.audit_integrity import append as append_audit

import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from services.error_codes import public_error
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.api.storage import (
    Store,
    processing_allowed,
    default_asset_root,
)
from services.asr.profiles import ASRProfile, load_profiles
from services.api.contracts import (
    Identity,
)
from services.api.time_utils import now


def create_app(
    db_path: str,
    credentials: dict[str, Identity],
    asset_root: str | None = None,
    asr_profiles: dict[str, ASRProfile] | None = None,
) -> FastAPI:
    from services.offline import validate_profile

    validate_profile()
    from services.api.auth import Settings, GoogleSessions

    auth_settings = Settings.environment()
    if (auth_settings.mode == "local" and not credentials) or any(
        len(token) < 32 for token in credentials
    ):
        raise ValueError("Configure service tokens of at least 32 characters")
    # Only digests are retained by the authentication closure.
    identities = {
        hashlib.sha256(k.encode()).hexdigest(): v for k, v in credentials.items()
    }
    database = Store(db_path).transaction
    profiles = dict(asr_profiles or {})
    if any(key != profile.profile_id for key, profile in profiles.items()):
        raise ValueError("ASR profile keys must match their profile IDs")
    with database() as con:
        for profile in profiles.values():
            con.execute(
                "INSERT OR IGNORE INTO asr_profiles VALUES (?,?)",
                (profile.sha256, profile.model_dump_json()),
            )
    assets = Path(asset_root or default_asset_root(db_path))
    assets.mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="Med Transcript AI",
        version="0.5.0",
        docs_url=None if auth_settings.production else "/docs",
        redoc_url=None if auth_settings.production else "/redoc",
        openapi_url=None if auth_settings.production else "/openapi.json",
    )
    sessions = GoogleSessions(auth_settings, database, Identity)
    app.state.auth_sessions = sessions
    sessions.register(app)
    from services.api.request_limits import RequestLimits

    app.add_middleware(RequestLimits)
    bearer = HTTPBearer(auto_error=False)

    @app.middleware("http")
    async def response_headers(request: Request, call_next):
        request.state.request_id = str(uuid4())
        if (
            auth_settings.production
            and request.headers.get("host") != urlsplit(auth_settings.origin).netloc
        ):
            response = JSONResponse({"code": "untrusted_host"}, status_code=400)
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = (
            "camera=(), geolocation=(), microphone=(self)"
        )
        if auth_settings.production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Default validation responses can echo sensitive submitted values.
        return JSONResponse(
            status_code=422,
            content={
                "code": "invalid_request",
                "request_id": request.state.request_id,
                "guidance": "Check the request against the OpenAPI schema.",
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        safe_error = public_error(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": safe_error["error_code"],
                "request_id": request.state.request_id,
            },
            headers=exc.headers,
        )

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request, exc):
        return JSONResponse(
            status_code=503,
            content={
                "code": "storage_unavailable",
                "request_id": request.state.request_id,
            },
            headers={"Retry-After": "2"},
        )

    if db_path.startswith(("postgresql://", "postgres://")):
        import psycopg

        app.add_exception_handler(psycopg.OperationalError, database_error)

    def identity(
        request: Request, auth: HTTPAuthorizationCredentials | None = Depends(bearer)
    ):
        if auth_settings.mode == "google":
            return sessions.principal(request)
        if auth:
            digest = hashlib.sha256(auth.credentials.encode()).hexdigest()
            for candidate, principal in identities.items():
                if secrets.compare_digest(digest, candidate):
                    if principal.role == "viewer" and request.method not in (
                        "GET",
                        "HEAD",
                        "OPTIONS",
                    ):
                        raise HTTPException(403, "read_only_account")
                    return principal
        raise HTTPException(
            401, "authentication_required", headers={"WWW-Authenticate": "Bearer"}
        )

    def encounter(con, encounter_id, actor):
        row = con.execute(
            "SELECT * FROM encounters WHERE id=? AND tenant=? AND clinician=?",
            (str(encounter_id), str(actor.tenant_id), str(actor.clinician_id)),
        ).fetchone()
        if row is None or row["deleted_at"]:
            raise HTTPException(404, "encounter_not_found")
        return row

    def audit(con, actor, action, resource):
        append_audit(
            con,
            (
                str(uuid4()),
                str(actor.tenant_id),
                str(actor.clinician_id),
                action,
                resource,
                now(),
            ),
        )

    def replay(con, actor, operation, key, body):
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        fingerprint = hashlib.sha256(
            json.dumps(
                body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        scope = (str(actor.tenant_id), str(actor.clinician_id), operation, key_hash)
        row = con.execute(
            "SELECT * FROM idempotency WHERE tenant=? AND actor=? AND operation=? AND key_hash=?",
            scope,
        ).fetchone()
        if row and datetime.fromisoformat(row["expires_at"]) <= datetime.now(
            timezone.utc
        ):
            con.execute(
                "DELETE FROM idempotency WHERE tenant=? AND actor=? AND operation=? AND key_hash=?",
                scope,
            )
            row = None
        if row and row["fingerprint"] != fingerprint:
            raise HTTPException(409, "idempotency_conflict")
        return scope, fingerprint, json.loads(row["response"]) if row else None

    def remember(con, scope, fingerprint, response):
        con.execute(
            "INSERT INTO idempotency VALUES (?,?,?,?,?,?,?)",
            (
                *scope,
                fingerprint,
                json.dumps(response),
                (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
            ),
        )

    def require_processing(con, encounter_id):
        lifecycle = con.execute(
            "SELECT stage FROM encounter_lifecycle WHERE encounter=?",
            (str(encounter_id),),
        ).fetchone()
        if lifecycle and lifecycle["stage"] == "revoked":
            raise HTTPException(409, "encounter_revoked")
        if not processing_allowed(con, encounter_id):
            raise HTTPException(403, "authorization_required")

    def upload_row(con, encounter_id, upload_id, actor):
        encounter(con, encounter_id, actor)
        row = con.execute(
            "SELECT * FROM uploads WHERE id=? AND encounter=?",
            (str(upload_id), str(encounter_id)),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "upload_not_found")
        return row

    def require_live_upload(row):
        if datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            raise HTTPException(409, "upload_expired")

    from services.api.router_context import ApiServices
    from services.api.routers import (
        encounters,
        authorizations,
        audio,
        jobs,
        transcripts,
    )

    api_services = ApiServices(
        database,
        identity,
        encounter,
        audit,
        replay,
        remember,
        require_processing,
        upload_row,
        require_live_upload,
        assets,
        profiles,
    )
    for router in (encounters, authorizations, audio, jobs, transcripts):
        router.register(app, api_services)

    from services.api.resumable import register as register_resumable

    register_resumable(
        app,
        database,
        identity,
        upload_row,
        require_processing,
        require_live_upload,
        assets,
        audit,
        replay,
    )
    from services.api.live_uploads import register as register_live_uploads

    register_live_uploads(
        app,
        database,
        identity,
        encounter,
        upload_row,
        require_processing,
        require_live_upload,
        assets,
        audit,
        replay,
        remember,
    )

    from services.review.routes import register_review_routes

    register_review_routes(
        app,
        database,
        identity,
        encounter,
        audit,
        require_processing,
        assets,
        profiles,
        replay,
    )
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    frontend = Path(__file__).resolve().parents[2] / "apps" / "clinician-web" / "dist"
    if frontend.is_dir():
        app.mount(
            "/assets", StaticFiles(directory=frontend / "assets"), name="web-assets"
        )

        @app.get("/", include_in_schema=False)
        def clinician_web():
            return FileResponse(frontend / "index.html")

        @app.get("/investor-demo", include_in_schema=False)
        def investor_demo():
            return FileResponse(frontend / "index.html")

    return app


def app_from_env():
    """Uvicorn factory; credentials are provisioned by operator, never by clients."""
    raw = os.environ.get("MED_TRANSCRIPT_IDENTITIES")
    if not raw:
        raise RuntimeError(
            "MED_TRANSCRIPT_IDENTITIES must contain a token-to-identity JSON object"
        )
    identities = {
        token: Identity.model_validate(value)
        for token, value in json.loads(raw).items()
    }
    profile_path = os.environ.get("MED_TRANSCRIPT_ASR_PROFILES")
    return create_app(
        os.environ.get("MED_TRANSCRIPT_DB", "data/development.sqlite3"),
        identities,
        os.environ.get("MED_TRANSCRIPT_ASSETS"),
        load_profiles(profile_path) if profile_path else None,
    )
