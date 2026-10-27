"""Separate, local-only ASR worker. Model profiles are registered by the API operator."""

import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Thread, Lock
from uuid import uuid4

from services.api.ingest import MAX_CHANNELS, file_sha256, inspect_pcm_wav
from services.api.storage import Store, processing_allowed, default_asset_root
from services.asr.adapter import ASRFailure, FasterWhisperAdapter
from services.asr.profiles import ASRProfile, canonical_json, content_sha256
from services.asr.transcripts import build_transcript


LEASE_SECONDS = 300
MAX_ATTEMPTS = 3


class Lease:
    def __init__(self, store, job_id, token, encounter_id):
        self.store, self.job_id, self.token, self.encounter_id = store, job_id, token, encounter_id
        self.shutdown = Event()
        self.failure = None
        self.check_lock=Lock();self.last_check=-float('inf')
        self.checkpoint_calls=0;self.db_checkpoints=0;self.checkpoint_seconds=0.0
        self.thread = Thread(target=self._heartbeat, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.shutdown.set()
        self.thread.join(timeout=15)

    def _heartbeat(self):
        while not self.shutdown.wait(20):
            try:
                self.checkpoint(force=True)
            except (ASRFailure, sqlite3.Error):
                self.failure = "worker_lease_lost"
                return

    def checkpoint(self,*,force=False):
        # Audio may be copied much faster than realtime. Database leases track wall
        # time; renewing once per audio second causes writer starvation on long files.
        with self.check_lock:
            self.checkpoint_calls+=1
            if self.failure:raise ASRFailure(self.failure)
            if not force and time.monotonic()-self.last_check<1.0:return
            started=time.perf_counter();self.db_checkpoints+=1
            try:
                with self.store.transaction() as con:
                    row=con.execute("SELECT * FROM jobs WHERE id=?",(self.job_id,)).fetchone()
                    stamp=datetime.now(timezone.utc)
                    if row["status"]!="running" or row["lease_token"]!=self.token or datetime.fromisoformat(row["lease_expires_at"])<=stamp:
                        raise ASRFailure("worker_lease_lost")
                    if not processing_allowed(con,self.encounter_id):raise ASRFailure("authorization_required")
                    con.execute("UPDATE jobs SET lease_expires_at=?,updated_at=? WHERE id=?",((stamp+timedelta(seconds=LEASE_SECONDS)).isoformat(),stamp.isoformat(),self.job_id))
                self.last_check=time.monotonic()
            finally:self.checkpoint_seconds+=time.perf_counter()-started


def run_once(db_path, asset_root, adapter_factory=FasterWhisperAdapter, diarization_manifest=None):
    store = Store(db_path)
    stamp, token = datetime.now(timezone.utc), str(uuid4())
    with store.transaction() as con:
        for abandoned in con.execute("SELECT * FROM jobs WHERE stage='transcription' AND status='running' AND lease_expires_at<=?", (stamp.isoformat(),)).fetchall():
            con.execute("INSERT OR IGNORE INTO job_attempts VALUES (?,?,?,?,?,?)", (abandoned["id"],abandoned["encounter"],abandoned["attempts"],"abandoned","worker_lease_expired",stamp.isoformat()))
        con.execute("""UPDATE jobs SET status=CASE WHEN attempts >= ? THEN 'failed' ELSE 'queued' END,
            error_code=CASE WHEN attempts >= ? THEN 'worker_retry_exhausted' ELSE NULL END,
            lease_token=NULL,lease_expires_at=NULL,updated_at=?
            WHERE stage='transcription' AND status='running' AND lease_expires_at <= ?""",
            (MAX_ATTEMPTS, MAX_ATTEMPTS, stamp.isoformat(), stamp.isoformat()))
        # One heavy inference job per database, across workers sharing that database.
        if con.execute("SELECT 1 FROM jobs WHERE stage='transcription' AND status='running' LIMIT 1").fetchone():
            return None
        job = con.execute("""SELECT * FROM jobs WHERE stage='transcription' AND status='queued'
            ORDER BY created_at,id LIMIT 1""").fetchone()
        if job is None:
            return None
        if not processing_allowed(con, job["encounter"]):
            con.execute("UPDATE jobs SET status='cancelled',error_code='authorization_required',updated_at=? WHERE id=?",
                        (stamp.isoformat(), job["id"]))
            return {"id": job["id"], "status": "cancelled"}
        con.execute("""UPDATE jobs SET status='running', attempts=attempts+1,lease_token=?,
            lease_expires_at=?,updated_at=? WHERE id=?""", (token,
            (stamp + timedelta(seconds=LEASE_SECONDS)).isoformat(), stamp.isoformat(), job["id"]))
        upload = con.execute("SELECT * FROM uploads WHERE id=?", (job["upload"],)).fetchone()
        profile_body = con.execute("SELECT body FROM asr_profiles WHERE sha256=?", (job["profile_sha256"],)).fetchone()[0]

    raw, metadata, profile, error, speaker_report = None, None, None, None, None
    work_started=time.perf_counter()
    with Lease(store, job["id"], token, job["encounter"]) as lease:
        try:
            profile = ASRProfile.model_validate_json(profile_body)
            if profile.sha256 != job["profile_sha256"]:
                raise ASRFailure("model_integrity_failure")
            try:
                profile.verify_artifacts()
            except (OSError, ValueError):
                raise ASRFailure("model_integrity_failure") from None
            source = Path(asset_root) / f"{upload['id']}.wav"
            if source.stat().st_size != upload["expected_bytes"] or file_sha256(source) != upload["expected_sha256"]:
                raise ASRFailure("asset_integrity_failure")
            with store.transaction() as con:
                ingest_row = con.execute("SELECT result FROM jobs WHERE upload=? AND stage='audio_ingest' AND status='succeeded'", (upload["id"],)).fetchone()
                ingest = json.loads(ingest_row["result"]) if ingest_row else {}
            if ingest.get("working_filename"):
                # The filename is generated from the upload ID, not trusted from model output.
                source = Path(asset_root) / f"{upload['id']}.normalized.wav"
                if file_sha256(source) != ingest["working_sha256"]:
                    raise ASRFailure("asset_integrity_failure")
            metadata = inspect_pcm_wav(source)
            metadata["sha256"] = upload["expected_sha256"]
            metadata["working_sha256"] = ingest.get("working_sha256")
            metadata["timeline_mapping_status"] = ingest.get("timeline_mapping_status", "original_pcm_timeline")
            if not 1 <= metadata["channels"] <= MAX_CHANNELS or metadata["sample_rate"] != 16000:
                raise ASRFailure("unsupported_asr_input")
            lease.checkpoint()
            adapter = adapter_factory(profile)
            if metadata["channels"] > 1:
                from services.asr.channels import transcribe_channels
                input_digest = metadata.get("working_sha256") or metadata["sha256"]
                def load_channel(channel, pcm_hash):
                    lease.checkpoint(force=True)
                    with store.transaction() as con:
                        saved = con.execute("SELECT * FROM asr_checkpoints WHERE job=? AND channel_index=?", (job["id"], channel)).fetchone()
                    if saved is None:
                        return None
                    if saved["input_sha256"] != input_digest or saved["profile_sha256"] != profile.sha256:
                        raise ASRFailure("asset_integrity_failure")
                    value = json.loads(saved["body"])
                    if content_sha256(value) != saved["sha256"] or value.get("isolated_channel_pcm_sha256") != pcm_hash:
                        raise ASRFailure("asset_integrity_failure")
                    build_transcript(value, metadata, job["encounter"], job["upload"], profile, str(uuid4()), 0)
                    return value
                def save_channel(channel, value):
                    build_transcript(value, metadata, job["encounter"], job["upload"], profile, str(uuid4()), 0)
                    lease.checkpoint(force=True)
                    with store.transaction() as con:
                        current = con.execute("SELECT lease_token,status FROM jobs WHERE id=?", (job["id"],)).fetchone()
                        if current["lease_token"] != token or current["status"] != "running" or not processing_allowed(con, job["encounter"]):
                            raise ASRFailure("worker_lease_lost")
                        con.execute("INSERT INTO asr_checkpoints VALUES (?,?,?,?,?,?,?,?)", (job["id"], job["encounter"], channel,
                            input_digest, profile.sha256, canonical_json(value), content_sha256(value), datetime.now(timezone.utc).isoformat()))
                raw = transcribe_channels(source, metadata, adapter, lease.checkpoint, load_channel, save_channel)
            else:
                raw = adapter.transcribe(source, metadata, lease.checkpoint)
            manifest_path = diarization_manifest or os.environ.get('MED_TRANSCRIPT_DIARIZATION_MANIFEST')
            if manifest_path and metadata["channels"] == 1 and not job["preview_only"]:
                from services.diarization import diarize
                speaker_report = diarize(source, json.loads(Path(manifest_path).read_text(encoding='utf-8')), lease.checkpoint)
            lease.checkpoint()
        except ASRFailure as exc:
            error = exc.code
        except OSError:
            error = "asset_unavailable"
        except Exception:
            # Provider/runtime exceptions can contain recognized text or file details.
            error = "asr_failed"

    with store.transaction() as con:
        current = con.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
        finished = datetime.now(timezone.utc)
        if current["status"] != "running" or current["lease_token"] != token:
            return {"id": job["id"], "status": current["status"]}
        if datetime.fromisoformat(current["lease_expires_at"]) <= finished:
            return {"id": job["id"], "status": "running"}
        result = None
        current_tx = con.execute("SELECT current_transcript FROM encounters WHERE id=?", (job["encounter"],)).fetchone()[0]
        if current_tx != job["expected_transcript_id"]:
            status, error = "cancelled", "transcript_changed"
        elif not processing_allowed(con, job["encounter"]):
            status, error = "cancelled", "authorization_required"
        else:
            if error is None:
                version = con.execute("SELECT COALESCE(MAX(version),0)+1 FROM transcript_versions WHERE encounter=?",
                                      (job["encounter"],)).fetchone()[0]
                transcript_id = str(uuid4())
                try:
                    from services.asr.channels import build_channels
                    builder = build_channels if isinstance(raw, dict) and "channel_outputs" in raw else build_transcript
                    body = builder(raw, metadata, job["encounter"], job["upload"], profile, transcript_id, version)
                    body["provenance"]["worker_timing"]={"wall_seconds":time.perf_counter()-work_started,
                        "lease_checkpoint_calls":lease.checkpoint_calls,"lease_database_checks":lease.db_checkpoints,
                        "lease_checkpoint_seconds":lease.checkpoint_seconds,"minimum_checkpoint_interval_seconds":1.0}
                    if speaker_report is not None:
                        from services.diarization import attach_speakers
                        body = attach_speakers(body, speaker_report)
                    if job["preview_only"]:
                        offset=job["timeline_offset_ms"]
                        result={"status":"provisional_not_a_source_version","approvable":False,
                            "profile_sha256":profile.sha256,"input_sha256":metadata["sha256"],
                            "provisional_segments":[{**segment,"start_ms":segment["start_ms"]+offset,"end_ms":segment["end_ms"]+offset,
                                "role":"unknown","role_status":"unconfirmed"} for segment in body["segments"]]}
                    else:
                        digest = content_sha256(body)
                        con.execute("INSERT INTO transcript_versions VALUES (?,?,?,?,?,?,?,?)",
                            (transcript_id, job["encounter"], job["upload"], job["id"], version,
                             digest, canonical_json(body), finished.isoformat()))
                        con.execute("UPDATE encounters SET current_transcript=? WHERE id=?", (transcript_id, job["encounter"]))
                        result = {"transcript_version_id": transcript_id, "sha256": digest,
                                  "transcript_url": f"/v1/encounters/{job['encounter']}/transcripts/{transcript_id}"}
                except ASRFailure as exc:
                    error = exc.code
            status = "failed" if error else "succeeded"
        con.execute("INSERT OR IGNORE INTO job_attempts VALUES (?,?,?,?,?,?)", (job["id"],job["encounter"],current["attempts"],status,error,finished.isoformat()))
        con.execute("""UPDATE jobs SET status=?,error_code=?,result=?,lease_token=NULL,
            lease_expires_at=NULL,updated_at=? WHERE id=?""",
            (status, error, json.dumps(result) if result else None, finished.isoformat(), job["id"]))
        owner = con.execute("SELECT tenant FROM encounters WHERE id=?", (job["encounter"],)).fetchone()
        con.execute("INSERT INTO audit VALUES (?,?,?,?,?,?)", (str(uuid4()), owner["tenant"],
                    "local_asr_worker", f"transcription_{status}", job["id"], finished.isoformat()))
    return {"id": job["id"], "status": status}


def main():
    parser = argparse.ArgumentParser(description="Process one queued local ASR job; never downloads model artifacts")
    parser.add_argument("--db", default="data/development.sqlite3")
    parser.add_argument("--assets", default=None)
    args = parser.parse_args()
    root = args.assets or default_asset_root(args.db)
    print(json.dumps(run_once(args.db, root) or {"status": "idle"}))


if __name__ == "__main__":
    main()
