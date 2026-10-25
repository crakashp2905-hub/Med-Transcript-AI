"""Launch the local synthetic workspace and its separate worker process."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from uuid import uuid4

import uvicorn

from services.api.main import Identity, create_app
from services.asr.profiles import load_profiles
from services.demo_fixture import create_fixture


def configure_local_features(local_drafting=False, public_diarization=False):
    if local_drafting:
        with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as response:
            models=json.load(response)['models']
        expected='65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b'
        if not any(m['name']=='qwen2.5:1.5b' and m['digest']==expected for m in models):
            raise ValueError('Provision the screened local Qwen digest before enabling drafting')
        os.environ.update(MED_TRANSCRIPT_DRAFTING_MODE='local',MED_TRANSCRIPT_LLM_ENABLED='1',
            MED_TRANSCRIPT_LLM_ENDPOINT='http://127.0.0.1:11434/v1/chat/completions',
            MED_TRANSCRIPT_LLM_MODEL='qwen2.5:1.5b',MED_TRANSCRIPT_LLM_STRUCTURED_SCHEMA='1',
            MED_TRANSCRIPT_LLM_TIMEOUT_SECONDS='60',MED_TRANSCRIPT_LLM_MAX_TOKENS='1024')
    if public_diarization:
        runtime=Path('data/diarization-runtime').resolve()
        manifest=Path('data/models/public-diarization-v1/manifest.json').resolve()
        if not manifest.is_file() or not (runtime/'sherpa_onnx').is_dir():
            raise ValueError('Provision the public diarization runtime and artifacts first')
        os.environ['MED_TRANSCRIPT_DIARIZATION_MANIFEST']=str(manifest)
        os.environ['PYTHONPATH']=str(runtime)+(os.pathsep+os.environ['PYTHONPATH'] if os.environ.get('PYTHONPATH') else '')


def main():
    parser = argparse.ArgumentParser(description="Start the synthetic clinician workspace on loopback")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1")
    parser.add_argument("--no-worker", action="store_true")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--open", action="store_true", help="Open the browser once the workspace is serving")
    parser.add_argument('--local-drafting',action='store_true',help='Enable screened local Qwen proposals, never automatic note approval')
    parser.add_argument('--public-diarization',action='store_true',help='Enable experimental public VAD/embedding speaker clustering')
    args = parser.parse_args()
    configure_local_features(args.local_drafting,args.public_diarization)
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
    profile_path = os.environ.get("MED_TRANSCRIPT_ASR_PROFILES") or config.get("asr_profiles_path")
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
        if args.open:
            def open_workspace():
                url = f"http://127.0.0.1:{args.port}"
                for _ in range(60):
                    try:
                        with urllib.request.urlopen(url, timeout=1) as response:
                            if response.status == 200:
                                webbrowser.open(url)
                                return
                    except OSError:
                        pass
                    time.sleep(0.5)
            threading.Thread(target=open_workspace, daemon=True).start()
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
