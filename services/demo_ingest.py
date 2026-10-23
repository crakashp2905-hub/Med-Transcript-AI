"""Offline synthetic smoke demonstration; run with the dev dependencies installed."""

import hashlib
import io
import json
import secrets
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from services.api.ingest import run_once
from services.api.main import Identity, create_app


def main():
    root = Path("data") / f"demo-{uuid4()}"
    path = str(root / "demo.sqlite3")
    token = secrets.token_urlsafe(32)
    credentials = {token: Identity(tenant_id=uuid4(), clinician_id=uuid4())}
    auth = {"Authorization": f"Bearer {token}"}
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(b"\0\0" * 16000)
    content = buffer.getvalue()

    def checked(response):
        response.raise_for_status()
        return response.json()

    with TestClient(create_app(path, credentials)) as client:
        encounter = checked(client.post("/v1/encounters", headers={**auth, "Idempotency-Key": str(uuid4())},
            json={"patient_reference_id": str(uuid4()), "patient_identifiers_confirmed": True, "synthetic_data": True}))
        route = f"/v1/encounters/{encounter['id']}"
        checked(client.post(route + "/authorizations", headers=auth, json={
            "scopes": ["recording", "local_processing"], "method": "written",
            "policy_version": "synthetic-demo-v1",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}))
        upload = checked(client.post(route + "/audio-uploads",
            headers={**auth, "Idempotency-Key": str(uuid4())},
            json={"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}))
        checked(client.put(upload["content_url"], headers={**auth, "Content-Type": "audio/wav"}, content=content))
        job = checked(client.post(route + f"/audio-uploads/{upload['id']}/complete", headers=auth))
        run_once(path, str(root / "assets"))
        result = checked(client.get(job["status_url"], headers=auth))
        if result["status"] != "succeeded":
            raise RuntimeError("Synthetic ingest demonstration failed")
        print(json.dumps({"status": result["status"], "synthetic_audio": "one second of silence",
                          "result": result["result"], "asr_enabled": False}, indent=2))


if __name__ == "__main__":
    main()
