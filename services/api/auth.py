"""Google OIDC code + PKCE; opaque, revocable server sessions, invitation-only access."""

from services.audit_integrity import append as append_audit
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
from pathlib import Path
import secrets
import shutil
import tempfile
import threading
import time
from urllib.parse import urlencode, urlsplit
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from services.api.authorization_policy import authorize_role_request


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def storage_access_status(path, *, file_required=False):
    """Report basic local filesystem access without exposing a configured path."""
    if path is None:
        return "remote_not_checked"
    try:
        target = Path(path)
        parent = target.parent if file_required else target
        accessible = parent.is_dir() and os.access(parent, os.R_OK | os.W_OK | os.X_OK)
        if file_required:
            accessible = (
                accessible and target.is_file() and os.access(target, os.R_OK | os.W_OK)
            )
    except (OSError, ValueError):
        accessible = False
    return "available" if accessible else "unavailable"


@dataclass
class Settings:
    mode: str = "local"
    production: bool = False
    origin: str = ""
    client_id: str = ""
    client_secret: str = ""
    members_file: str = ""
    domain: str = ""
    member_lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @classmethod
    def environment(cls):
        value = cls(
            os.getenv("MED_TRANSCRIPT_AUTH_MODE", "local"),
            os.getenv("MED_TRANSCRIPT_ENV") == "production",
            os.getenv("MED_TRANSCRIPT_PUBLIC_ORIGIN", ""),
            os.getenv("GOOGLE_CLIENT_ID", ""),
            os.getenv("GOOGLE_CLIENT_SECRET", ""),
            os.getenv("MED_TRANSCRIPT_MEMBERS_FILE", ""),
            os.getenv("GOOGLE_WORKSPACE_DOMAIN", ""),
        )
        secret_file = os.getenv("GOOGLE_CLIENT_SECRET_FILE")
        if secret_file:
            value.client_secret = Path(secret_file).read_text(encoding="utf-8").strip()
        if value.mode not in ("local", "google"):
            raise ValueError("Unknown authentication mode")
        if value.production and value.mode != "google":
            raise ValueError("Hosted production requires Google authentication")
        if value.mode == "google":
            parsed = urlsplit(value.origin)
            local = parsed.hostname in ("127.0.0.1", "localhost")
            if (
                (
                    parsed.scheme != "https"
                    and not (local and not value.production and parsed.scheme == "http")
                )
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
                or not parsed.hostname
            ):
                raise ValueError(
                    "Configure an exact HTTPS public origin (HTTP loopback only for development)"
                )
            if not all((value.client_id, value.client_secret, value.members_file)):
                raise ValueError(
                    "Google client credentials and membership file are required"
                )
            value.members()  # Refuse malformed/missing invitation configuration at startup.
        return value

    @property
    def secure(self):
        return self.origin.startswith("https://")

    @property
    def cookie(self):
        return "__Host-med_session" if self.secure else "med_session"

    def members(self):
        document = self.read_member_document()
        rows = document["users"]
        result = {}
        user_ids = set()
        for row in rows:
            email = row["email"].lower()
            if (
                email in result
                or row["role"]
                not in ("clinician", "physician", "scribe", "administrator", "viewer")
                or "@" not in email
            ):
                raise ValueError("Invalid invitation")
            UUID(row["tenant_id"])
            UUID(row["clinician_id"])
            if row["role"] == "scribe":
                if not isinstance(row.get("user_id"), str):
                    raise ValueError("Scribe invitation requires a separate user_id")
                user_id = UUID(row["user_id"])
                if user_id == UUID(row["clinician_id"]):
                    raise ValueError(
                        "Scribe identity must differ from assigned clinician"
                    )
            elif row.get("user_id") is not None:
                user_id = UUID(row["user_id"])
            else:
                user_id = None
            if row.get("user_id") is not None:
                if user_id in user_ids:
                    raise ValueError("Membership user IDs must be unique")
                user_ids.add(user_id)
            result[email] = row
        return result

    def read_member_document(self):
        path = Path(self.members_file)
        if not self.members_file or path.is_symlink() or not path.is_file():
            raise ValueError("Membership configuration is unavailable")
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(
            document.get("users"), list
        ):
            raise ValueError("Invalid membership configuration")
        return document

    def write_member_document(self, document):
        path = Path(self.members_file)
        if path.is_symlink() or not path.is_file():
            raise OSError("membership_configuration_not_writable")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as target:
                temporary = Path(target.name)
                json.dump(document, target, indent=2, ensure_ascii=False)
                target.write("\n")
                target.flush()
                os.fsync(target.fileno())
            try:
                os.chmod(temporary, path.stat().st_mode & 0o777)
            except OSError:
                pass
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


class GoogleSessions:
    def __init__(self, settings, database, identity_type):
        self.settings, self.database, self.identity_type = (
            settings,
            database,
            identity_type,
        )

    def limited(self, request, action, limit):
        stamp = int(time.time())
        # Forwarded headers are never trusted for throttling.
        bucket = digest(
            f"{action}:{request.client.host if request.client else 'unknown'}:{stamp // 60}"
        )
        with self.database() as con:
            con.execute("DELETE FROM auth_throttle WHERE expires_at<?", (stamp,))
            row = con.execute(
                "SELECT hits FROM auth_throttle WHERE bucket=?", (bucket,)
            ).fetchone()
            if row and row["hits"] >= limit:
                raise HTTPException(
                    429, "sign_in_rate_limited", headers={"Retry-After": "60"}
                )
            if row:
                con.execute(
                    "UPDATE auth_throttle SET hits=hits+1 WHERE bucket=?", (bucket,)
                )
            else:
                con.execute(
                    "INSERT INTO auth_throttle VALUES (?,?,?)", (bucket, 1, stamp + 120)
                )

    def member(self, email, subject):
        try:
            entry = self.settings.members().get(email)
        except (OSError, ValueError, KeyError):
            raise HTTPException(503, "invitation_configuration_unavailable") from None
        if not entry or (entry.get("sub") and entry["sub"] != subject):
            raise HTTPException(403, "invitation_required")
        return self.identity_type(
            tenant_id=entry["tenant_id"],
            clinician_id=entry["clinician_id"],
            user_id=entry.get("user_id"),
            role=entry["role"],
        )

    def principal(self, request):
        token = request.cookies.get(self.settings.cookie, "")
        if not token or len(token) > 256:
            raise HTTPException(401, "authentication_required")
        stamp = int(time.time())
        with self.database() as con:
            row = con.execute(
                "SELECT * FROM auth_sessions WHERE token_hash=?", (digest(token),)
            ).fetchone()
            if (
                not row
                or row["expires_at"] <= stamp
                or row["last_seen"] + 1800 <= stamp
            ):
                raise HTTPException(401, "session_expired")
            actor = self.member(row["email"], row["subject"])
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                if request.headers.get(
                    "origin"
                ) != self.settings.origin or not secrets.compare_digest(
                    request.headers.get("x-csrf-token", ""), digest(token + ":csrf")
                ):
                    raise HTTPException(403, "csrf_validation_failed")
            authorize_role_request(actor, request.method, request.url.path)
            if stamp - row["last_seen"] >= 60:
                con.execute(
                    "UPDATE auth_sessions SET last_seen=? WHERE token_hash=?",
                    (stamp, digest(token)),
                )
        return actor

    def exchange(self, code, verifier, nonce):
        import requests
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2.id_token import verify_oauth2_token

        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "redirect_uri": self.settings.origin + "/v1/auth/callback",
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
            timeout=15,
            allow_redirects=False,
        )
        response.raise_for_status()

        class BoundedRequest(GoogleRequest):
            def __call__(self, *args, **kwargs):
                kwargs["timeout"] = 10
                return super().__call__(*args, **kwargs)

        claims = verify_oauth2_token(
            response.json()["id_token"], BoundedRequest(), self.settings.client_id
        )
        # google-auth verifies signature, expiry, audience, issued-at and issuer.
        if (
            not secrets.compare_digest(str(claims.get("nonce", "")), nonce)
            or claims.get("email_verified") is not True
            or (self.settings.domain and claims.get("hd") != self.settings.domain)
            or (
                not self.settings.domain
                and str(claims.get("email", "")).lower().split("@")[-1]
                not in ("gmail.com", "googlemail.com")
            )
            or not isinstance(claims.get("sub"), str)
            or not claims["sub"]
            or claims.get("azp", self.settings.client_id) != self.settings.client_id
        ):
            raise ValueError("Invalid Google identity claims")
        return claims

    def register(self, app):
        from services.api.contracts import AdminUserCreate

        settings = self.settings

        def admin_actor(request):
            actor = self.principal(request)
            if actor.role != "administrator":
                raise HTTPException(403, "administrator_role_required")
            return actor

        @app.get("/v1/admin/diagnostics")
        def admin_diagnostics(request: Request):
            admin_actor(request)
            database_path = request.app.state.diagnostic_database_path
            asset_path = request.app.state.diagnostic_asset_path
            try:
                disk_free_bytes = shutil.disk_usage(asset_path).free
                storage_status = "measured"
            except OSError:
                disk_free_bytes = None
                storage_status = "unavailable"
            root = Path.cwd()
            return {
                "schema_version": "clinic_operator_diagnostics_v1",
                "runtime": {
                    "python": platform.python_version(),
                    "platform": platform.system(),
                    "node": shutil.which("node") is not None,
                    "npm": shutil.which("npm") is not None,
                    "docker": shutil.which("docker") is not None,
                    "psql": shutil.which("psql") is not None,
                },
                "storage": {
                    "status": storage_status,
                    "free_bytes": disk_free_bytes,
                    "access": {
                        "database": storage_access_status(
                            database_path, file_required=database_path is not None
                        ),
                        "assets": storage_access_status(asset_path),
                    },
                    "backup_restore": "not_checked",
                },
                "frontend_dependencies": (
                    "available"
                    if (root / "apps/clinician-web/node_modules/typescript").is_dir()
                    else "missing"
                ),
                "offline_mode": (
                    "enabled"
                    if os.getenv("MED_TRANSCRIPT_OFFLINE") == "1"
                    else "not_confirmed"
                ),
                "model_inference_performed": False,
                "external_services_contacted": False,
                "patient_or_encounter_data_included": False,
            }

        def public_member(row):
            return {
                "email": row["email"].lower(),
                "user_id": str(UUID(row.get("user_id") or row["clinician_id"])),
                "clinician_id": str(UUID(row["clinician_id"])),
                "tenant_id": str(UUID(row["tenant_id"])),
                "role": row["role"],
            }

        def append_member_audit(document, actor, action, target_user_id):
            events = document.setdefault("audit_log", [])
            if not isinstance(events, list):
                raise HTTPException(503, "membership_audit_unavailable")
            events.append(
                {
                    "tenant_id": str(actor.tenant_id),
                    "actor_user_id": str(actor.actor_id),
                    "action": action,
                    "target_user_id": str(target_user_id),
                    "time": datetime.now(timezone.utc).isoformat(),
                }
            )
            document["audit_log"] = events[-500:]

        @app.get("/v1/auth/config")
        def config():
            return {
                "mode": settings.mode,
                "google_enabled": settings.mode == "google",
                "local_key_enabled": settings.mode == "local",
                "provider_label": "Google Workspace" if settings.domain else "Google",
            }

        @app.get("/v1/admin/users")
        def admin_users(request: Request):
            actor = admin_actor(request)
            try:
                with settings.member_lock:
                    members = settings.members()
            except (OSError, ValueError, KeyError, TypeError):
                raise HTTPException(
                    503, "membership_configuration_unavailable"
                ) from None
            return {
                "users": [
                    public_member(row)
                    for row in members.values()
                    if row["tenant_id"] == str(actor.tenant_id)
                ]
            }

        @app.get("/v1/admin/users/audit")
        def admin_user_audit(request: Request):
            actor = admin_actor(request)
            try:
                with settings.member_lock:
                    document = settings.read_member_document()
            except (OSError, ValueError, json.JSONDecodeError):
                raise HTTPException(
                    503, "membership_configuration_unavailable"
                ) from None
            events = document.get("audit_log", [])
            if not isinstance(events, list):
                raise HTTPException(503, "membership_audit_unavailable")
            return {
                "events": [
                    event
                    for event in events
                    if event.get("tenant_id") == str(actor.tenant_id)
                ][-100:]
            }

        @app.post("/v1/admin/users", status_code=201)
        def add_admin_user(request: Request, body: AdminUserCreate):
            actor = admin_actor(request)
            with settings.member_lock:
                try:
                    document = settings.read_member_document()
                    members = settings.members()
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                    raise HTTPException(
                        503, "membership_configuration_unavailable"
                    ) from None
                if body.email in members:
                    raise HTTPException(409, "user_already_invited")
                rows = document["users"]
                if body.role in ("scribe", "viewer"):
                    if body.assigned_clinician_id is None:
                        raise HTTPException(422, "assigned_clinician_required")
                    assigned = any(
                        row["tenant_id"] == str(actor.tenant_id)
                        and row["role"] in ("clinician", "physician")
                        and row["clinician_id"] == str(body.assigned_clinician_id)
                        for row in rows
                    )
                    if not assigned:
                        raise HTTPException(404, "assigned_clinician_not_found")
                    clinician_id = body.assigned_clinician_id
                else:
                    if body.assigned_clinician_id is not None:
                        raise HTTPException(422, "assigned_clinician_not_allowed")
                    clinician_id = uuid4()
                user_id = uuid4()
                new_member = {
                    "email": body.email,
                    "tenant_id": str(actor.tenant_id),
                    "clinician_id": str(clinician_id),
                    "user_id": str(user_id),
                    "role": body.role,
                }
                rows.append(new_member)
                append_member_audit(document, actor, "user_invited", user_id)
                try:
                    settings.write_member_document(document)
                except OSError:
                    raise HTTPException(
                        503, "membership_configuration_not_writable"
                    ) from None
            return public_member(new_member)

        @app.delete("/v1/admin/users/{user_id}", status_code=200)
        def remove_admin_user(user_id: UUID, request: Request):
            actor = admin_actor(request)
            email = None
            with settings.member_lock:
                try:
                    document = settings.read_member_document()
                    members = settings.members()
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                    raise HTTPException(
                        503, "membership_configuration_unavailable"
                    ) from None
                selected = next(
                    (
                        row
                        for row in members.values()
                        if row["tenant_id"] == str(actor.tenant_id)
                        and UUID(row.get("user_id") or row["clinician_id"]) == user_id
                    ),
                    None,
                )
                if selected is None:
                    raise HTTPException(404, "user_not_found")
                if user_id == actor.actor_id:
                    raise HTTPException(409, "cannot_remove_current_administrator")
                tenant_admins = [
                    row
                    for row in members.values()
                    if row["tenant_id"] == str(actor.tenant_id)
                    and row["role"] == "administrator"
                ]
                if selected["role"] == "administrator" and len(tenant_admins) <= 1:
                    raise HTTPException(409, "last_administrator_required")
                email = selected["email"].lower()
                document["users"] = [
                    row for row in document["users"] if row["email"].lower() != email
                ]
                append_member_audit(document, actor, "user_removed", user_id)
                try:
                    settings.write_member_document(document)
                except OSError:
                    raise HTTPException(
                        503, "membership_configuration_not_writable"
                    ) from None
            with self.database() as con:
                con.execute("DELETE FROM auth_sessions WHERE email=?", (email,))
            return {"removed_user_id": str(user_id), "access_revoked": True}

        @app.get("/v1/auth/login")
        def login(request: Request):
            if settings.mode != "google":
                raise HTTPException(404, "google_sign_in_not_configured")
            self.limited(request, "login", 20)
            state, binding, verifier, nonce = (
                secrets.token_urlsafe(32) for _ in range(4)
            )
            stamp = int(time.time())
            with self.database() as con:
                con.execute("DELETE FROM auth_flows WHERE expires_at<?", (stamp,))
                con.execute(
                    "DELETE FROM auth_sessions WHERE expires_at<? OR last_seen<?",
                    (stamp, stamp - 1800),
                )
                con.execute(
                    "INSERT INTO auth_flows VALUES (?,?,?,?,?)",
                    (digest(state), digest(binding), verifier, nonce, stamp + 300),
                )
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                .rstrip(b"=")
                .decode()
            )
            response = RedirectResponse(
                "https://accounts.google.com/o/oauth2/v2/auth?"
                + urlencode(
                    {
                        "client_id": settings.client_id,
                        "redirect_uri": settings.origin + "/v1/auth/callback",
                        "response_type": "code",
                        "scope": "openid email",
                        "state": state,
                        "nonce": nonce,
                        "code_challenge": challenge,
                        "code_challenge_method": "S256",
                        "hd": settings.domain,
                        "prompt": "select_account",
                    }
                ),
                status_code=302,
            )
            response.set_cookie(
                "med_login",
                binding,
                max_age=300,
                secure=settings.secure,
                httponly=True,
                samesite="lax",
                path="/v1/auth",
            )
            return response

        @app.get("/v1/auth/callback")
        def callback(request: Request):
            if settings.mode != "google":
                raise HTTPException(404, "google_sign_in_not_configured")
            self.limited(request, "callback", 40)
            state, code = (
                request.query_params.get("state", ""),
                request.query_params.get("code", ""),
            )
            if not state or len(state) > 128 or not code or len(code) > 4096:
                raise HTTPException(400, "invalid_sign_in_response")
            with self.database() as con:
                row = con.execute(
                    "SELECT * FROM auth_flows WHERE state_hash=?", (digest(state),)
                ).fetchone()
                if (
                    not row
                    or row["expires_at"] <= time.time()
                    or not secrets.compare_digest(
                        row["binding_hash"],
                        digest(request.cookies.get("med_login", "")),
                    )
                ):
                    raise HTTPException(400, "invalid_or_expired_sign_in_state")
                con.execute(
                    "DELETE FROM auth_flows WHERE state_hash=?", (digest(state),)
                )
            try:
                claims = self.exchange(code, row["verifier"], row["nonce"])
                email, subject = claims["email"].lower(), claims["sub"]
                actor = self.member(email, subject)
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(401, "google_identity_validation_failed") from None
            token, stamp = secrets.token_urlsafe(32), int(time.time())
            with self.database() as con:
                prior = con.execute(
                    "SELECT subject FROM auth_subjects WHERE email=?", (email,)
                ).fetchone()
                if prior and prior["subject"] != subject:
                    raise HTTPException(403, "invitation_subject_changed")
                con.execute(
                    "INSERT OR IGNORE INTO auth_subjects VALUES (?,?)", (email, subject)
                )
                old = request.cookies.get(settings.cookie)
                if old:
                    con.execute(
                        "DELETE FROM auth_sessions WHERE token_hash=?", (digest(old),)
                    )
                con.execute(
                    "INSERT INTO auth_sessions VALUES (?,?,?,?,?)",
                    (digest(token), email, subject, stamp + 28800, stamp),
                )
                append_audit(
                    con,
                    (
                        str(uuid4()),
                        str(actor.tenant_id),
                        str(actor.actor_id),
                        "google_sign_in",
                        "session",
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            response = RedirectResponse("/", status_code=303)
            response.delete_cookie("med_login", path="/v1/auth")
            response.set_cookie(
                settings.cookie,
                token,
                max_age=28800,
                secure=settings.secure,
                httponly=True,
                samesite="lax",
                path="/",
            )
            return response

        @app.get("/v1/auth/session")
        def session(request: Request):
            if settings.mode != "google":
                raise HTTPException(404, "google_sign_in_not_configured")
            actor = self.principal(request)
            return {
                "csrf_token": digest(request.cookies[settings.cookie] + ":csrf"),
                "role": actor.role,
            }

        @app.post("/v1/auth/logout")
        def logout(request: Request):
            if settings.mode != "google":
                raise HTTPException(404, "google_sign_in_not_configured")
            token = request.cookies.get(settings.cookie, "")
            if token:
                if len(token) > 256:
                    raise HTTPException(401, "authentication_required")
                if request.headers.get(
                    "origin"
                ) != settings.origin or not secrets.compare_digest(
                    request.headers.get("x-csrf-token", ""), digest(token + ":csrf")
                ):
                    raise HTTPException(403, "csrf_validation_failed")
                # Repeated logout is safe even when the first response was lost.
                with self.database() as con:
                    con.execute(
                        "DELETE FROM auth_sessions WHERE token_hash=?",
                        (digest(token),),
                    )
            response = JSONResponse({"signed_out": True})
            response.delete_cookie(
                settings.cookie,
                path="/",
                secure=settings.secure,
                httponly=True,
                samesite="lax",
            )
            return response
