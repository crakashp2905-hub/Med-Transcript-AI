"""Explicitly synthetic loopback browser fixture; never an ASR accuracy result."""

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4


class ScriptedAdapter:
    """Return a fixed test sentence regardless of audio. No model is executed."""

    def __init__(self, profile):
        self.profile = profile

    def transcribe(self, source, metadata, checkpoint):
        checkpoint()
        duration = metadata["duration_ms"] / 1000
        return {
            "duration_seconds": duration,
            "inference_executed": False,
            "runtime_packages": {"fixture": "scripted_non_asr_v1"},
            "segments": [
                {
                    "start_seconds": 0,
                    "end_seconds": min(duration, 2),
                    "text": "Developer scripted fixture: patient reports vomiting. Patient denies fever.",
                }
            ],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-scripted-non-asr", required=True, action="store_true")
    parser.add_argument("--port", type=int, default=8004)
    args = parser.parse_args()
    if os.getenv("MED_TRANSCRIPT_ENV") == "production":
        raise ValueError("scripted_fixture_forbidden_in_production")
    os.environ.update(
        MED_TRANSCRIPT_OFFLINE="1",
        MED_TRANSCRIPT_PROFILE="no_external_dependency",
        MED_TRANSCRIPT_AUTH_MODE="local",
        MED_TRANSCRIPT_DRAFTING_MODE="deterministic",
    )
    from services.offline import install

    install()
    from services.api.main import create_app, Identity
    from services.api.ingest import run_once as ingest
    from services.asr.worker import run_once as transcribe
    from services.asr.profiles import ASRProfile
    import uvicorn

    config = json.loads(Path("data/local-config.json").read_text(encoding="utf-8"))
    root = (Path("data") / f"offline-browser-{uuid4()}").resolve()
    root.mkdir()
    for name in ("demo-sample.wav", "demo-sample.json"):
        shutil.copyfile(Path("data") / name, root / name)
    db, assets = str(root / "fixture.sqlite3"), str(root / "assets")
    marker = b"developer_scripted_fixture_no_model_weights"
    model = root / "scripted-markers"
    model.mkdir()
    artifacts = {}
    for name in ("model.bin", "config.json", "tokenizer.json"):
        (model / name).write_bytes(marker)
        artifacts[name] = hashlib.sha256(marker).hexdigest()
    profile = ASRProfile(
        profile_id="scripted-non-asr-test-only",
        model_dir=str(model),
        source="developer_scripted_fixture_NO_MODEL_NO_ACCURACY_CLAIM",
        revision="0" * 40,
        license_id="test-only-no-weights",
        artifacts=artifacts,
    )
    profile.verify_artifacts()
    app = create_app(
        db,
        {
            config["access_key"]: Identity(
                tenant_id=config["tenant_id"], clinician_id=config["clinician_id"]
            )
        },
        assets,
        {profile.profile_id: profile},
    )
    stop = Event()

    def work():
        while not stop.wait(0.1):
            ingest(db, assets)
            transcribe(db, assets, adapter_factory=ScriptedAdapter)

    worker = Thread(target=work, daemon=True)
    worker.start()
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
    finally:
        stop.set()
        worker.join(timeout=10)


if __name__ == "__main__":
    main()
