"""Opt-in localhost-only simulated OIDC provider fixture. Not included in the image."""

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-simulated-provider", action="store_true", required=True
    )
    parser.add_argument("--port", type=int, default=8003)
    args = parser.parse_args()
    if (
        not args.allow_simulated_provider
        or os.getenv("MED_TRANSCRIPT_ENV") == "production"
    ):
        raise ValueError("Simulated provider is forbidden in production")
    from services.api.main import create_app
    import uvicorn

    root = Path("data") / f"google-browser-test-{uuid4()}"
    root.mkdir(parents=True, exist_ok=False)
    tenant, clinician = str(uuid4()), str(uuid4())
    members = [
        {
            "email": email,
            "sub": subject,
            "role": role,
            "tenant_id": tenant,
            "clinician_id": (
                clinician if role in {"physician", "viewer"} else str(uuid4())
            ),
            "user_id": str(uuid4()),
        }
        for email, subject, role in [
            ("clinician@example.org", "clinician-sub", "physician"),
            ("investor@example.org", "viewer-sub", "viewer"),
            ("administrator@example.org", "administrator-sub", "administrator"),
        ]
    ]
    path = root / "members.json"
    path.write_text(json.dumps({"users": members}), encoding="utf-8")
    os.environ.pop("GOOGLE_CLIENT_SECRET_FILE", None)
    os.environ.update(
        MED_TRANSCRIPT_AUTH_MODE="google",
        MED_TRANSCRIPT_PUBLIC_ORIGIN=f"http://127.0.0.1:{args.port}",
        GOOGLE_CLIENT_ID="simulated-browser-client",
        GOOGLE_CLIENT_SECRET="simulated-test-only",
        GOOGLE_WORKSPACE_DOMAIN="example.org",
        MED_TRANSCRIPT_MEMBERS_FILE=str(path),
    )
    app = create_app(
        str(root / "database.sqlite3"),
        {},
        str(Path("data") / f"google-test-assets-{uuid4()}"),
    )
    identities = {
        "viewer": ("investor@example.org", "viewer-sub"),
        "clinician": ("clinician@example.org", "clinician-sub"),
        "administrator": ("administrator@example.org", "administrator-sub"),
        "scribe": ("scribe@example.org", "scribe-sub"),
    }

    def exchange(code, verifier, nonce):
        email, subject = identities.get(code, identities["clinician"])
        return {"email": email, "sub": subject}

    app.state.auth_sessions.exchange = exchange
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
