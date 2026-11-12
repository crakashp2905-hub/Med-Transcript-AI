"""Google OIDC code + PKCE; opaque, revocable server sessions, invitation-only access."""

from services.audit_integrity import append as append_audit
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlencode, urlsplit
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass
class Settings:
    mode: str = "local"
    production: bool = False
    origin: str = ""
    client_id: str = ""
    client_secret: str = ""
    members_file: str = ""
    domain: str = ""

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
        rows = json.loads(Path(self.members_file).read_text(encoding="utf-8"))["users"]
        result = {}
        for row in rows:
            email = row["email"].lower()
            if (
                email in result
                or row["role"] not in ("clinician", "viewer")
                or "@" not in email
            ):
                raise ValueError("Invalid invitation")
            UUID(row["tenant_id"])
            UUID(row["clinician_id"])
            result[email] = row
        return result


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
                if actor.role == "viewer" and request.url.path != "/v1/auth/logout":
                    raise HTTPException(403, "read_only_account")
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
        settings = self.settings

        @app.get("/v1/auth/config")
        def config():
            return {
                "mode": settings.mode,
                "google_enabled": settings.mode == "google",
                "local_key_enabled": settings.mode == "local",
                "provider_label": "Google Workspace" if settings.domain else "Google",
            }

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
                        str(actor.clinician_id),
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
            actor = self.principal(request)
            with self.database() as con:
                con.execute(
                    "DELETE FROM auth_sessions WHERE token_hash=?",
                    (digest(request.cookies[settings.cookie]),),
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
