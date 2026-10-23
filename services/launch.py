"""Launch the local synthetic workspace and its separate worker process."""

import argparse
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import uvicorn

from services.api.main import Identity, create_app
from services.asr.profiles import load_profiles
from services.demo_fixture import create_fixture


def main():
    parser = argparse.ArgumentParser(description="Start the synthetic clinician workspace on loopback")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1")
    parser.add_argument("--no-worker", action="store_true")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    root = Path("data")
    root.mkdir(exist_ok=True)
    config_path = root / "local-config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        config = {"access_key": secrets.token_urlsafe(32), "tenant_id": str(uuid4()), "clinician_id": str(uuid4())}
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    if args.demo:
        print("Synthetic example ready." if create_fixture(root) else "Synthetic voice unavailable; upload your own synthetic WAV.")
    db = os.environ.get("MED_TRANSCRIPT_DB", str(root / "development.sqlite3"))
    profile_path = os.environ.get("MED_TRANSCRIPT_ASR_PROFILES")
    profiles = load_profiles(profile_path) if profile_path else {}
    app = create_app(db, {config["access_key"]: Identity(tenant_id=config["tenant_id"], clinician_id=config["clinician_id"])},
        os.environ.get("MED_TRANSCRIPT_ASSETS"), profiles)
    print(f"Workspace: http://127.0.0.1:{args.port}\nLocal access key: {config['access_key']}", flush=True)
    process = None
    log = None
    if not args.no_worker:
        log = (root / "worker.log").open("a", encoding="utf-8")
        command = [sys.executable, "-m", "services.worker_loop", "--db", db]
        if os.environ.get("MED_TRANSCRIPT_ASSETS"):
            command.extend(["--assets", os.environ["MED_TRANSCRIPT_ASSETS"]])
        process = subprocess.Popen(command, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    try:
        uvicorn.run(app, host=args.host, port=args.port, access_log=False)
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if log:
            log.close()


if __name__ == "__main__":
    main()
