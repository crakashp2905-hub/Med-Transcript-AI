"""Bounded PCM WAV inspection. No general codec decoder or inference."""

import argparse
import hashlib
import json
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from services.api.storage import Store, processing_allowed


MAX_UPLOAD_BYTES = 250_000_000
MAX_DURATION_SECONDS = 3600
MAX_ATTEMPTS = 3


class InvalidAudio(ValueError):
    pass


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_pcm_wav(path):
    size = Path(path).stat().st_size
    if size < 44 or size > MAX_UPLOAD_BYTES:
        raise InvalidAudio("invalid_media")
    with open(path, "rb") as source:
        header = source.read(12)
        if header[:4] != b"RIFF" or header[8:] != b"WAVE" or struct.unpack("<I", header[4:8])[0] + 8 != size:
            raise InvalidAudio("invalid_media")
        fmt, data_size, chunks = None, None, 0
        while source.tell() < size:
            chunks += 1
            chunk_header = source.read(8)
            if len(chunk_header) != 8 or chunks > 1024:
                raise InvalidAudio("invalid_media")
            kind, length = struct.unpack("<4sI", chunk_header)
            end = source.tell() + length + (length % 2)
            if end > size:
                raise InvalidAudio("invalid_media")
            if kind == b"fmt ":
                if fmt is not None or length not in (16, 18):
                    raise InvalidAudio("unsupported_media")
                fmt = struct.unpack("<HHIIHH", source.read(16))
                if length == 18 and source.read(2) != b"\0\0":
                    raise InvalidAudio("unsupported_media")
            elif kind == b"data":
                if fmt is None or data_size is not None:
                    raise InvalidAudio("invalid_media")
                data_size = length
            source.seek(end)
        if fmt is None or data_size is None:
            raise InvalidAudio("invalid_media")
        codec, channels, sample_rate, byte_rate, block_align, bits = fmt
        if codec != 1 or channels not in (1, 2) or bits != 16 or not 8000 <= sample_rate <= 48000:
            raise InvalidAudio("unsupported_media")
        if block_align != channels * 2 or byte_rate != sample_rate * block_align:
            raise InvalidAudio("invalid_media")
        if data_size == 0 or data_size % block_align:
            raise InvalidAudio("invalid_media")
        frames = data_size // block_align
        if frames > sample_rate * MAX_DURATION_SECONDS:
            raise InvalidAudio("duration_limit_exceeded")
        return {"codec": "pcm_s16le", "channels": channels, "sample_rate": sample_rate,
                "frames": frames, "duration_ms": frames * 1000 // sample_rate,
                "bytes": size, "source_availability": "available"}


def run_once(db_path: str, asset_root: str):
    """Claim one job with a bounded lease; publish only with current authorization."""
    store = Store(db_path)
    stamp = datetime.now(timezone.utc)
    token = str(uuid4())
    with store.transaction() as con:
        # Recover jobs abandoned by a stopped process, up to a bounded attempt count.
        con.execute("""UPDATE jobs SET status=CASE WHEN attempts >= ? THEN 'failed' ELSE 'queued' END,
            error_code=CASE WHEN attempts >= ? THEN 'worker_retry_exhausted' ELSE NULL END,
            lease_token=NULL, lease_expires_at=NULL, updated_at=?
            WHERE stage='audio_ingest' AND status='running' AND lease_expires_at <= ?""",
            (MAX_ATTEMPTS, MAX_ATTEMPTS, stamp.isoformat(), stamp.isoformat()))
        row = con.execute("SELECT * FROM jobs WHERE stage='audio_ingest' AND status='queued' ORDER BY created_at, id LIMIT 1").fetchone()
        if row is None:
            return None
        job_id = row["id"]
        if not processing_allowed(con, row["encounter"]):
            con.execute("UPDATE jobs SET status='cancelled', error_code='authorization_required', updated_at=? WHERE id=?",
                        (stamp.isoformat(), job_id))
            return {"id": job_id, "status": "cancelled"}
        con.execute("""UPDATE jobs SET status='running', attempts=attempts+1,
            lease_token=?, lease_expires_at=?, updated_at=? WHERE id=?""",
            (token, (stamp + timedelta(minutes=5)).isoformat(), stamp.isoformat(), job_id))
        upload = con.execute("SELECT * FROM uploads WHERE id=?", (row["upload"],)).fetchone()

    result, error = None, None
    try:
        source = Path(asset_root) / f"{upload['id']}.wav"
        if source.stat().st_size != upload["expected_bytes"] or file_sha256(source) != upload["expected_sha256"]:
            raise InvalidAudio("asset_integrity_failure")
        result = inspect_pcm_wav(source)
        result["sha256"] = upload["expected_sha256"]
    except InvalidAudio as exc:
        error = str(exc)
    except OSError:
        error = "asset_unavailable"

    with store.transaction() as con:
        current = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        finished = datetime.now(timezone.utc)
        if current["status"] != "running" or current["lease_token"] != token:
            return {"id": job_id, "status": current["status"]}
        if datetime.fromisoformat(current["lease_expires_at"]) <= finished:
            return {"id": job_id, "status": "running"}  # Later claim recovers the expired lease.
        if not processing_allowed(con, row["encounter"]):
            status, error, result = "cancelled", "authorization_required", None
        else:
            status = "failed" if error else "succeeded"
        con.execute("""UPDATE jobs SET status=?, error_code=?, result=?, lease_token=NULL,
            lease_expires_at=NULL, updated_at=? WHERE id=?""",
            (status, error, json.dumps(result) if result else None, finished.isoformat(), job_id))
        owner = con.execute("SELECT tenant, clinician FROM encounters WHERE id=?", (row["encounter"],)).fetchone()
        con.execute("INSERT INTO audit VALUES (?,?,?,?,?,?)", (str(uuid4()), owner["tenant"],
                    "local_ingest_worker", f"ingest_{status}", job_id, finished.isoformat()))
    return {"id": job_id, "status": status}


def main():
    parser = argparse.ArgumentParser(description="Inspect one queued synthetic PCM WAV upload; no ASR")
    parser.add_argument("--db", default="data/development.sqlite3")
    parser.add_argument("--assets", default=None)
    args = parser.parse_args()
    root = args.assets or str(Path(args.db).parent / "assets")
    print(json.dumps(run_once(args.db, root) or {"status": "idle"}))


if __name__ == "__main__":
    main()
