import hashlib
import io
import json
import wave
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from services.api.storage import Store
from services.api.ingest import run_once


def wav_bytes():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 1600)
    return buffer.getvalue()


def seed_queued_audio_job(database, asset_root, *, revoked=False):
    stamp = datetime.now(timezone.utc)
    encounter_id, authorization_id, upload_id, job_id = map(
        str, (uuid4(), uuid4(), uuid4(), uuid4())
    )
    tenant_id, clinician_id = str(uuid4()), str(uuid4())
    body = json.dumps(
        {
            "scopes": ["recording", "local_processing"],
            "expires_at": (stamp + timedelta(hours=1)).isoformat(),
        }
    )
    payload = wav_bytes()
    source = asset_root / f"{upload_id}.wav"
    source.write_bytes(payload)

    with Store(str(database)).transaction() as con:
        con.execute(
            "INSERT INTO encounters(id,tenant,clinician,body,created_at) VALUES (?,?,?,?,?)",
            (
                encounter_id,
                tenant_id,
                clinician_id,
                "{}",
                stamp.isoformat(),
            ),
        )
        con.execute(
            "INSERT INTO authorizations(id,encounter,body,created_at,withdrawn_at) VALUES (?,?,?,?,?)",
            (
                authorization_id,
                encounter_id,
                body,
                stamp.isoformat(),
                stamp.isoformat() if revoked else None,
            ),
        )
        con.execute(
            "INSERT INTO uploads(id,encounter,expected_bytes,expected_sha256,status,created_at,expires_at) VALUES (?,?,?,?,?,?,?)",
            (
                upload_id,
                encounter_id,
                len(payload),
                hashlib.sha256(payload).hexdigest(),
                "uploaded",
                stamp.isoformat(),
                (stamp + timedelta(hours=1)).isoformat(),
            ),
        )
        con.execute(
            "INSERT INTO jobs(id,upload,encounter,status,attempts,created_at,updated_at,stage) VALUES (?,?,?,?,?,?,?,?)",
            (
                job_id,
                upload_id,
                encounter_id,
                "queued",
                0,
                stamp.isoformat(),
                stamp.isoformat(),
                "audio_ingest",
            ),
        )
    return encounter_id, authorization_id, upload_id, job_id


def test_withdrawn_consent_cancels_queued_worker_before_audio_processing(
    tmp_path, monkeypatch
):
    database = tmp_path / "state.sqlite3"
    assets = tmp_path / "assets"
    assets.mkdir()
    _, _, _, job_id = seed_queued_audio_job(database, assets, revoked=True)
    monkeypatch.setattr(
        "services.api.ingest.inspect_pcm_wav",
        lambda *_args: (_ for _ in ()).throw(AssertionError("audio must not be read")),
    )

    assert run_once(str(database), str(assets)) == {
        "id": job_id,
        "status": "cancelled",
    }
    with Store(str(database)).transaction() as con:
        job = con.execute(
            "SELECT status,result FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
        assert job["status"] == "cancelled" and job["result"] is None
        assert (
            con.execute("SELECT COUNT(*) FROM transcript_versions").fetchone()[0] == 0
        )


def test_revocation_during_worker_processing_blocks_result_publication(
    tmp_path, monkeypatch
):
    database = tmp_path / "state.sqlite3"
    assets = tmp_path / "assets"
    assets.mkdir()
    _, authorization_id, _, job_id = seed_queued_audio_job(database, assets)

    def inspect_then_revoke(_source):
        with Store(str(database)).transaction() as con:
            con.execute(
                "UPDATE authorizations SET withdrawn_at=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), authorization_id),
            )
        return {
            "sample_rate": 16000,
            "channels": 1,
            "duration_ms": 100,
            "frames": 1600,
        }

    monkeypatch.setattr("services.api.ingest.inspect_pcm_wav", inspect_then_revoke)

    result = run_once(str(database), str(assets))

    assert result == {"id": job_id, "status": "cancelled"}
    with Store(str(database)).transaction() as con:
        job = con.execute(
            "SELECT status,result FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
        assert job["status"] == "cancelled" and job["result"] is None
        assert (
            con.execute("SELECT COUNT(*) FROM transcript_versions").fetchone()[0] == 0
        )
