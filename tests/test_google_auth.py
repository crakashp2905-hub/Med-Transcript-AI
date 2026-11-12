import json, time
from uuid import uuid4
from urllib.parse import urlsplit, parse_qs
import pytest
from fastapi.testclient import TestClient
from services.api.main import create_app, Identity
from services.api.auth import digest, Settings


@pytest.fixture
def google_app(tmp_path, monkeypatch):
    member = {
        "email": "investor@example.org",
        "sub": "google-sub",
        "tenant_id": str(uuid4()),
        "clinician_id": str(uuid4()),
        "role": "viewer",
    }
    path = tmp_path / "members.json"
    path.write_text(json.dumps({"users": [member]}))
    for k, v in {
        "MED_TRANSCRIPT_AUTH_MODE": "google",
        "MED_TRANSCRIPT_PUBLIC_ORIGIN": "https://scribe.example.org",
        "GOOGLE_CLIENT_ID": "client",
        "GOOGLE_CLIENT_SECRET": "secret",
        "MED_TRANSCRIPT_MEMBERS_FILE": str(path),
        "GOOGLE_WORKSPACE_DOMAIN": "example.org",
        "MED_TRANSCRIPT_ENV": "production",
    }.items():
        monkeypatch.setenv(k, v)
    app = create_app(
        str(tmp_path / "auth.sqlite3"),
        {
            "a" * 40: Identity(
                tenant_id=member["tenant_id"], clinician_id=member["clinician_id"]
            )
        },
    )
    app.state.auth_sessions.exchange = lambda code, verifier, nonce: {
        "email": member["email"],
        "sub": member["sub"],
    }
    client = TestClient(
        app, base_url="https://scribe.example.org", follow_redirects=False
    )
    return client, app, path, member


def sign_in(client):
    response = client.get("/v1/auth/login")
    assert response.status_code == 302
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"] and query["scope"] == [
        "openid email"
    ]
    return client.get(
        "/v1/auth/callback",
        params={"state": query["state"][0], "code": "authorization-code"},
    )


def test_google_session_cookie_csrf_roles_logout_and_replay(google_app):
    client, app, path, member = google_app
    assert (
        client.get(
            "/v1/session", headers={"Authorization": "Bearer " + "a" * 40}
        ).status_code
        == 401
    )
    assert sign_in(client).status_code == 303
    cookie = client.cookies.get("__Host-med_session")
    assert cookie
    session = client.get("/v1/auth/session").json()
    assert session["role"] == "viewer"
    assert client.get("/v1/session").json()["tenant_id"] == member["tenant_id"]
    assert client.post("/v1/demo").status_code == 403
    h = {"Origin": "https://scribe.example.org", "X-CSRF-Token": session["csrf_token"]}
    assert client.post("/v1/demo", headers=h).json()["code"] == "read_only_account"
    assert (
        client.post(
            "/v1/auth/logout", headers={**h, "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert client.post("/v1/auth/logout", headers=h).status_code == 200
    client.cookies.set("__Host-med_session", cookie)
    assert client.get("/v1/session").status_code == 401


def test_state_binding_replay_and_cookie_flags(google_app):
    client, app, _, _ = google_app
    response = client.get("/v1/auth/login")
    state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
    assert (
        "HttpOnly" in response.headers["set-cookie"]
        and "Secure" in response.headers["set-cookie"]
    )
    binding = client.cookies.get("med_login")
    client.cookies.clear()
    assert (
        client.get(
            "/v1/auth/callback", params={"state": state, "code": "code"}
        ).status_code
        == 400
    )
    client.cookies.set("med_login", binding)
    result = client.get("/v1/auth/callback", params={"state": state, "code": "code"})
    assert result.status_code == 303
    assert (
        "HttpOnly" in result.headers["set-cookie"]
        and "SameSite=lax" in result.headers["set-cookie"]
    )
    assert (
        client.get(
            "/v1/auth/callback", params={"state": state, "code": "code"}
        ).status_code
        == 400
    )


def test_invitation_revocation_idle_expiry_and_subject_pinning(google_app):
    client, app, path, member = google_app
    assert sign_in(client).status_code == 303
    path.write_text(json.dumps({"users": []}))
    assert client.get("/v1/session").status_code == 403
    path.write_text(json.dumps({"users": [member]}))
    with app.state.auth_sessions.database() as con:
        con.execute("UPDATE auth_sessions SET last_seen=?", (int(time.time()) - 1801,))
    assert client.get("/v1/session").status_code == 401
    app.state.auth_sessions.exchange = lambda *args: {
        "email": member["email"],
        "sub": "different",
    }
    # Pinned invitation rejects changes before session creation.
    assert sign_in(client).status_code == 403


def test_production_guards_and_sign_in_throttle(google_app):
    client, app, _, _ = google_app
    assert client.get("/docs").status_code == 404
    r = client.get("/health")
    assert r.headers["strict-transport-security"] == "max-age=31536000"
    assert r.headers["x-frame-options"] == "DENY"
    assert client.get("/health", headers={"host": "evil.example"}).status_code == 400
    for _ in range(20):
        assert client.get("/v1/auth/login").status_code == 302
    assert client.get("/v1/auth/login").status_code == 429


def test_production_refuses_local_keys_and_unsafe_origin(monkeypatch):
    monkeypatch.setenv("MED_TRANSCRIPT_ENV", "production")
    monkeypatch.setenv("MED_TRANSCRIPT_AUTH_MODE", "local")
    with pytest.raises(ValueError):
        Settings.environment()
    monkeypatch.setenv("MED_TRANSCRIPT_AUTH_MODE", "google")
    monkeypatch.setenv("MED_TRANSCRIPT_PUBLIC_ORIGIN", "http://example.org")
    with pytest.raises(ValueError):
        Settings.environment()


@pytest.mark.parametrize(
    "field,value",
    [
        ("nonce", "wrong"),
        ("email_verified", False),
        ("hd", "evil.example"),
        ("azp", "other-client"),
        ("sub", ""),
    ],
)
def test_google_claims_rejected(google_app, monkeypatch, field, value):
    _, app, _, _ = google_app
    import requests
    import google.oauth2.id_token

    claims = {
        "nonce": "expected",
        "email_verified": True,
        "hd": "example.org",
        "azp": "client",
        "sub": "google-sub",
    }
    claims[field] = value

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"id_token": "signed-google-token"}

    monkeypatch.setattr(requests, "post", lambda *a, **k: Response())
    monkeypatch.setattr(
        google.oauth2.id_token, "verify_oauth2_token", lambda *a, **k: claims
    )
    from services.api.auth import GoogleSessions

    with pytest.raises(ValueError):
        GoogleSessions.exchange(app.state.auth_sessions, "code", "verifier", "expected")


def test_real_signed_google_id_token_and_forgery(google_app, monkeypatch):
    _, app, _, _ = google_app
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from google.auth import crypt, jwt
    from google.auth.transport import requests as transport
    import requests

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        .decode()
    )
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "client",
        "sub": "subject",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
        "nonce": "expected",
        "email_verified": True,
        "hd": "example.org",
        "email": "investor@example.org",
    }
    encoded = jwt.encode(
        crypt.RSASigner.from_string(pem, key_id="key"), claims
    ).decode()

    class TokenResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"id_token": encoded}

    class CertResponse:
        status = 200
        data = json.dumps({"key": public}).encode()

    monkeypatch.setattr(requests, "post", lambda *a, **k: TokenResponse())
    monkeypatch.setattr(transport.Request, "__call__", lambda *a, **k: CertResponse())
    from services.api.auth import GoogleSessions

    assert (
        GoogleSessions.exchange(
            app.state.auth_sessions, "code", "verifier", "expected"
        )["sub"]
        == "subject"
    )
    # Exercise the real signature/claims verifier with locally signed adversarial
    # tokens. Network boundaries remain mocked, rather than bypassing validation.
    valid = dict(claims)
    for patch in (
        {"aud": "another-client"},
        {"iss": "https://attacker.invalid"},
        {"nonce": "wrong-nonce"},
        {"exp": int(time.time()) - 3600},
        {"iat": int(time.time()) + 3600},
    ):
        encoded = jwt.encode(
            crypt.RSASigner.from_string(pem, key_id="key"), {**valid, **patch}
        ).decode()
        with pytest.raises(Exception):
            GoogleSessions.exchange(
                app.state.auth_sessions, "code", "verifier", "expected"
            )
    encoded = jwt.encode(crypt.RSASigner.from_string(pem, key_id="key"), valid).decode()
    parts = encoded.split(".")
    parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    encoded = ".".join(parts)
    with pytest.raises(Exception):
        GoogleSessions.exchange(app.state.auth_sessions, "code", "verifier", "expected")


def test_clinician_cookie_writes_require_csrf_and_persist_across_restart(google_app):
    client, app, path, member = google_app
    member["role"] = "clinician"
    path.write_text(json.dumps({"users": [member]}))
    assert sign_in(client).status_code == 303
    csrf = client.get("/v1/auth/session").json()["csrf_token"]
    data = {
        "patient_reference_id": str(uuid4()),
        "patient_identifiers_confirmed": True,
        "synthetic_data": True,
    }
    assert (
        client.post(
            "/v1/encounters", json=data, headers={"Idempotency-Key": str(uuid4())}
        ).status_code
        == 403
    )
    headers = {
        "Origin": "https://scribe.example.org",
        "X-CSRF-Token": csrf,
        "Idempotency-Key": str(uuid4()),
    }
    assert client.post("/v1/encounters", json=data, headers=headers).status_code == 201
    fresh = TestClient(
        create_app(str(path.parent / "auth.sqlite3"), {}),
        base_url="https://scribe.example.org",
    )
    fresh.cookies.update(client.cookies)
    assert fresh.get("/v1/encounters").json()["items"]
    with app.state.auth_sessions.database() as con:
        con.execute("UPDATE auth_sessions SET expires_at=0")
    assert fresh.get("/v1/session").status_code == 401


def test_oversized_json_is_rejected_with_and_without_content_length(google_app):
    client, _, _, _ = google_app
    response = client.post(
        "/v1/encounters",
        content=b"{}",
        headers={
            "content-type": "application/json",
            "content-length": str(9 * 1024 * 1024),
        },
    )
    assert response.status_code == 413
    response = client.post(
        "/v1/encounters",
        content=(b" " * 1024 * 1024 for _ in range(9)),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


@pytest.mark.parametrize(
    "email,accepted",
    [
        ("invited@gmail.com", True),
        ("invited@googlemail.com", True),
        ("invited@external.example", False),
    ],
)
def test_no_workspace_mode_only_accepts_verified_personal_google_domains(
    google_app, monkeypatch, email, accepted
):
    _, app, _, _ = google_app
    app.state.auth_sessions.settings.domain = ""
    import requests, google.oauth2.id_token
    from services.api.auth import GoogleSessions

    claims = {
        "email": email,
        "sub": "subject",
        "nonce": "nonce",
        "email_verified": True,
        "aud": "client",
        "azp": "client",
    }

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"id_token": "token"}

    monkeypatch.setattr(requests, "post", lambda *a, **k: Response())
    monkeypatch.setattr(
        google.oauth2.id_token, "verify_oauth2_token", lambda *a, **k: claims
    )
    if accepted:
        assert (
            GoogleSessions.exchange(
                app.state.auth_sessions, "code", "verifier", "nonce"
            )["email"]
            == email
        )
    else:
        with pytest.raises(ValueError):
            GoogleSessions.exchange(
                app.state.auth_sessions, "code", "verifier", "nonce"
            )
