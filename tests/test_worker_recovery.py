import hashlib
import io
import json
import subprocess
import sys
import wave
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from services.api.ingest import run_once as ingest_once
from services.api.storage import Store

from services.worker_recovery import recover


def _run_ingest_process(db_path, asset_root):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "services.api.ingest",
            "--db",
            db_path,
            "--assets",
            asset_root,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


def _seed_ingest(tmp_path):
    db_path = str(tmp_path / "concurrent-ingest.sqlite3")
    asset_root = tmp_path / "assets"
    asset_root.mkdir()
    body = io.BytesIO()
    with wave.open(body, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(b"\0\0" * 1600)
    content = body.getvalue()
    encounter, upload, job = str(uuid4()), str(uuid4()), str(uuid4())
    (asset_root / f"{upload}.wav").write_bytes(content)
    now = datetime.now(timezone.utc)
    with Store(db_path).transaction() as con:
        con.execute(
            "INSERT INTO encounters(id,tenant,clinician,body,created_at) VALUES(?,?,?,?,?)",
            (encounter, str(uuid4()), str(uuid4()), "{}", now.isoformat()),
        )
        con.execute(
            "INSERT INTO authorizations(id,encounter,body,created_at) VALUES(?,?,?,?)",
            (
                str(uuid4()),
                encounter,
                json.dumps(
                    {
                        "scopes": ["recording", "local_processing"],
                        "expires_at": (now + timedelta(hours=1)).isoformat(),
                    }
                ),
                now.isoformat(),
            ),
        )
        con.execute(
            "INSERT INTO uploads(id,encounter,expected_bytes,expected_sha256,status,created_at,expires_at,media_type,received_bytes) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                upload,
                encounter,
                len(content),
                hashlib.sha256(content).hexdigest(),
                "complete",
                now.isoformat(),
                (now + timedelta(hours=1)).isoformat(),
                "audio/wav",
                len(content),
            ),
        )
        con.execute(
            "INSERT INTO jobs(id,upload,encounter,status,created_at,updated_at,stage) VALUES(?,?,?,?,?,?,?)",
            (
                job,
                upload,
                encounter,
                "queued",
                now.isoformat(),
                now.isoformat(),
                "audio_ingest",
            ),
        )
    return db_path, str(asset_root), upload


def test_worker_recovery_reacquires_stale_lease_without_publishing():
    result = recover(stage="asr", lease_state="stale", checkpoint={"chunk": 3})
    assert result["action"] == "reacquire_lease"
    assert result["checkpoint"]["chunk"] == 3
    assert result["publish"] is False


def test_worker_recovery_rejects_invalid_lease_state():
    with pytest.raises(ValueError):
        recover(stage="asr", lease_state="bogus", checkpoint={})


def test_multiprocess_ingest_claim_publishes_once(tmp_path):
    db_path, asset_root, upload = _seed_ingest(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(
            pool.map(lambda _: _run_ingest_process(db_path, asset_root), range(2))
        )

    assert sum(outcome.get("status") == "succeeded" for outcome in outcomes) == 1
    assert sum(outcome.get("status") == "idle" for outcome in outcomes) == 1
    with Store(db_path).transaction() as con:
        job = con.execute(
            "SELECT status, attempts, result FROM jobs WHERE upload=? AND stage='audio_ingest'",
            (upload,),
        ).fetchone()
        audit_count = con.execute(
            "SELECT COUNT(*) FROM audit WHERE resource=(SELECT id FROM jobs WHERE upload=? AND stage='audio_ingest') AND action='ingest_succeeded'",
            (upload,),
        ).fetchone()[0]
    assert job["status"] == "succeeded"
    assert job["attempts"] == 1
    assert job["result"]
    assert audit_count == 1


def test_expired_ingest_lease_is_recovered_and_published_once(tmp_path):
    db_path, asset_root, upload = _seed_ingest(tmp_path)
    with Store(db_path).transaction() as con:
        con.execute(
            "UPDATE jobs SET status='running', attempts=1, lease_token='abandoned', lease_expires_at='2000-01-01T00:00:00+00:00', result=NULL WHERE upload=? AND stage='audio_ingest'",
            (upload,),
        )
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(
            pool.map(lambda _: ingest_once(db_path, asset_root), range(2))
        )

    with Store(db_path).transaction() as con:
        job = con.execute(
            "SELECT status, attempts FROM jobs WHERE upload=? AND stage='audio_ingest'",
            (upload,),
        ).fetchone()
        audit_count = con.execute(
            "SELECT COUNT(*) FROM audit WHERE resource=(SELECT id FROM jobs WHERE upload=? AND stage='audio_ingest') AND action='ingest_succeeded'",
            (upload,),
        ).fetchone()[0]
    assert any(outcome and outcome["status"] == "succeeded" for outcome in outcomes)
    assert job["status"] == "succeeded"
    assert job["attempts"] == 2
    assert audit_count == 1
