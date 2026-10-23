"""Offline synthetic smoke demonstration; run with the dev dependencies installed."""

import argparse
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
from services.asr.profiles import load_profiles
from services.asr.worker import run_once as transcribe_once


def main():
    parser = argparse.ArgumentParser(description="Offline synthetic upload/ingest demonstration, optionally with local ASR")
    parser.add_argument("--synthetic-audio", help="Optional synthetic PCM WAV fixture; do not use patient recordings")
    parser.add_argument("--asr-profiles", help="Optional operator-created JSON profile file; first profile is used")
    args = parser.parse_args()
    profiles = load_profiles(args.asr_profiles) if args.asr_profiles else {}
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
    content = Path(args.synthetic_audio).read_bytes() if args.synthetic_audio else buffer.getvalue()

    def checked(response):
        response.raise_for_status()
        return response.json()

    with TestClient(create_app(path, credentials, asr_profiles=profiles)) as client:
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
        report = {"status": result["status"], "synthetic_audio": "provided fixture" if args.synthetic_audio else "one second of silence",
                  "result": result["result"], "asr_enabled": bool(profiles)}
        if profiles:
            profile = next(iter(profiles.values()))
            queued = checked(client.post(route + "/transcriptions",
                headers={**auth, "Idempotency-Key": str(uuid4())},
                json={"audio_asset_id": upload["id"], "inference_profile_id": profile.profile_id}))
            transcribe_once(path, str(root / "assets"))
            completed = checked(client.get(queued["status_url"], headers=auth))
            if completed["status"] != "succeeded":
                raise RuntimeError(f"Synthetic ASR smoke failed: {completed['error_code']}")
            transcript = checked(client.get(completed["result"]["transcript_url"], headers=auth))
            report["transcription"] = {"status": completed["status"], "sha256": transcript["sha256"],
                "segments": len(transcript["segments"]), "review_flags": transcript["review_flags"],
                "inference_executed": transcript["provenance"]["inference_executed"]}
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
