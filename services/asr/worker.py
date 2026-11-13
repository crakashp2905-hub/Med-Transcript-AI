"""Separate, local-only ASR worker. Model profiles are registered by the API operator."""

from services.audit_integrity import append as append_audit

import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Thread, Lock
from uuid import uuid4
from contextlib import ExitStack
import tempfile
import wave

from services.api.ingest import MAX_CHANNELS, file_sha256, inspect_pcm_wav
from services.api.storage import Store, processing_allowed, default_asset_root
from services.asr.adapter import ASRFailure, FasterWhisperAdapter
from services.provider_interfaces import (
    DiarizationProvider,
    ProviderFailure,
    require_provider,
)
from services.asr.profiles import ASRProfile, canonical_json, content_sha256
from services.asr.transcripts import build_transcript
from services.audio_provenance import (
    crop_timeline,
    derive_provenance,
    file_sha256 as audio_file_sha256,
    source_provenance,
)


LEASE_SECONDS = 300
MAX_ATTEMPTS = 3


class Lease:
    def __init__(self, store, job_id, token, encounter_id):
        self.store, self.job_id, self.token, self.encounter_id = (
            store,
            job_id,
            token,
            encounter_id,
        )
        self.shutdown = Event()
        self.failure = None
        self.check_lock = Lock()
        self.last_check = -float("inf")
        self.checkpoint_calls = 0
        self.db_checkpoints = 0
        self.checkpoint_seconds = 0.0
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

    def checkpoint(self, *, force=False):
        # Audio may be copied much faster than realtime. Database leases track wall
        # time; renewing once per audio second causes writer starvation on long files.
        with self.check_lock:
            self.checkpoint_calls += 1
            if self.failure:
                raise ASRFailure(self.failure)
            if not force and time.monotonic() - self.last_check < 1.0:
                return
            started = time.perf_counter()
            self.db_checkpoints += 1
            try:
                with self.store.transaction() as con:
                    row = con.execute(
                        "SELECT * FROM jobs WHERE id=?", (self.job_id,)
                    ).fetchone()
                    stamp = datetime.now(timezone.utc)
                    if (
                        row["status"] != "running"
                        or row["lease_token"] != self.token
                        or datetime.fromisoformat(row["lease_expires_at"]) <= stamp
                    ):
                        raise ASRFailure("worker_lease_lost")
                    if not processing_allowed(con, self.encounter_id):
                        raise ASRFailure("authorization_required")
                    con.execute(
                        "UPDATE jobs SET lease_expires_at=?,updated_at=? WHERE id=?",
                        (
                            (stamp + timedelta(seconds=LEASE_SECONDS)).isoformat(),
                            stamp.isoformat(),
                            self.job_id,
                        ),
                    )
                self.last_check = time.monotonic()
            finally:
                self.checkpoint_seconds += time.perf_counter() - started


def run_once(
    db_path, asset_root, adapter_factory=FasterWhisperAdapter, diarization_manifest=None
):
    from services.inference_slot import local_inference_slot

    with local_inference_slot(requested_bytes=512 * 1024**2) as ready:
        if not ready:
            return {"status": "deferred", "error_code": "local_inference_busy"}
        return _run_once(db_path, asset_root, adapter_factory, diarization_manifest)


def _run_once(db_path, asset_root, adapter_factory, diarization_manifest):
    store = Store(db_path)
    stamp, token = datetime.now(timezone.utc), str(uuid4())
    with store.transaction() as con:
        for abandoned in con.execute(
            "SELECT * FROM jobs WHERE stage='transcription' AND status='running' AND lease_expires_at<=?",
            (stamp.isoformat(),),
        ).fetchall():
            con.execute(
                "INSERT OR IGNORE INTO job_attempts VALUES (?,?,?,?,?,?)",
                (
                    abandoned["id"],
                    abandoned["encounter"],
                    abandoned["attempts"],
                    "abandoned",
                    "worker_lease_expired",
                    stamp.isoformat(),
                ),
            )
        con.execute(
            """UPDATE jobs SET status=CASE WHEN attempts >= ? THEN 'failed' ELSE 'queued' END,
            error_code=CASE WHEN attempts >= ? THEN 'worker_retry_exhausted' ELSE NULL END,
            lease_token=NULL,lease_expires_at=NULL,updated_at=?
            WHERE stage='transcription' AND status='running' AND lease_expires_at <= ?""",
            (MAX_ATTEMPTS, MAX_ATTEMPTS, stamp.isoformat(), stamp.isoformat()),
        )
        # One heavy inference job per database, across workers sharing that database.
        if con.execute(
            "SELECT 1 FROM jobs WHERE stage='transcription' AND status='running' LIMIT 1"
        ).fetchone():
            return None
        job = con.execute("""SELECT * FROM jobs WHERE stage='transcription' AND status='queued'
            ORDER BY created_at,id LIMIT 1""").fetchone()
        if job is None:
            return None
        if not processing_allowed(con, job["encounter"]):
            con.execute(
                "UPDATE jobs SET status='cancelled',error_code='authorization_required',updated_at=? WHERE id=?",
                (stamp.isoformat(), job["id"]),
            )
            return {"id": job["id"], "status": "cancelled"}
        con.execute(
            """UPDATE jobs SET status='running', attempts=attempts+1,lease_token=?,
            lease_expires_at=?,updated_at=? WHERE id=?""",
            (
                token,
                (stamp + timedelta(seconds=LEASE_SECONDS)).isoformat(),
                stamp.isoformat(),
                job["id"],
            ),
        )
        upload = con.execute(
            "SELECT * FROM uploads WHERE id=?", (job["upload"],)
        ).fetchone()
        profile_body = con.execute(
            "SELECT body FROM asr_profiles WHERE sha256=?", (job["profile_sha256"],)
        ).fetchone()[0]

    raw, metadata, profile, error, speaker_report = None, None, None, None, None
    memory_admission_receipt = None
    work_started = time.perf_counter()
    span_request = (
        json.loads(job["retranscription"]) if job["retranscription"] else None
    )
    with ExitStack() as stack:
        lease = stack.enter_context(Lease(store, job["id"], token, job["encounter"]))
        try:
            profile = ASRProfile.model_validate_json(profile_body)
            if profile.sha256 != job["profile_sha256"]:
                raise ASRFailure("model_integrity_failure")
            availability = profile.availability()
            if availability["status"] != "available_not_admitted":
                raise ASRFailure(availability["reason_code"])
            source = Path(asset_root) / f"{upload['id']}.wav"
            if (
                source.stat().st_size != upload["expected_bytes"]
                or file_sha256(source) != upload["expected_sha256"]
            ):
                raise ASRFailure("asset_integrity_failure")
            with store.transaction() as con:
                ingest_row = con.execute(
                    "SELECT result FROM jobs WHERE upload=? AND stage='audio_ingest' AND status='succeeded'",
                    (upload["id"],),
                ).fetchone()
                ingest = json.loads(ingest_row["result"]) if ingest_row else {}
            if ingest.get("working_filename"):
                # The filename is generated from the upload ID, not trusted from model output.
                source = Path(asset_root) / f"{upload['id']}.normalized.wav"
                if file_sha256(source) != ingest["working_sha256"]:
                    raise ASRFailure("asset_integrity_failure")
            metadata = inspect_pcm_wav(source)
            metadata["sha256"] = upload["expected_sha256"]
            metadata["working_sha256"] = ingest.get("working_sha256")
            metadata["timeline_mapping_status"] = ingest.get(
                "timeline_mapping_status", "original_pcm_timeline"
            )
            metadata["audio_provenance"] = ingest.get("audio_provenance") or (
                source_provenance(source, upload["media_type"])
            )
            if (
                not 1 <= metadata["channels"] <= MAX_CHANNELS
                or metadata["sample_rate"] != 16000
            ):
                raise ASRFailure("unsupported_asr_input")
            if span_request:
                with store.transaction() as con:
                    saved = con.execute(
                        "SELECT sha256 FROM transcript_versions WHERE id=? AND encounter=?",
                        (job["expected_transcript_id"], job["encounter"]),
                    ).fetchone()
                    if (
                        saved is None
                        or saved["sha256"] != span_request["transcript_sha256"]
                    ):
                        raise ASRFailure("asset_integrity_failure")
                start, end = span_request["start_ms"], span_request["end_ms"]
                channel = (
                    span_request["channel_index"]
                    if span_request["channel_index"] is not None
                    else 0
                )
                if (
                    not 0 <= start < end <= metadata["duration_ms"]
                    or end - start > 120000
                    or channel >= metadata["channels"]
                ):
                    raise ASRFailure("unsupported_asr_input")
                directory = stack.enter_context(
                    tempfile.TemporaryDirectory(prefix="scribe-retranscribe-")
                )
                cropped = Path(directory) / "span.wav"
                with (
                    wave.open(str(source), "rb") as audio,
                    wave.open(str(cropped), "wb") as out,
                ):
                    audio.setpos(start * 16)
                    pcm = audio.readframes((end - start) * 16)
                    if metadata["channels"] > 1:
                        import numpy as np

                        pcm = (
                            np.frombuffer(pcm, dtype="<i2")
                            .reshape(-1, metadata["channels"])[:, channel]
                            .tobytes()
                        )
                    out.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                    out.writeframes(pcm)
                parent_provenance = metadata["audio_provenance"]
                if audio_file_sha256(source) != parent_provenance["asset_sha256"]:
                    raise ASRFailure("asset_integrity_failure")
                timeline = crop_timeline(start * 16, end * 16, 16000)
                timeline.update(
                    kind="channel_crop_sample_index_offset"
                    if metadata["channels"] > 1
                    else "crop_sample_index_offset",
                    channel_index=channel,
                    source_channel_count=metadata["channels"],
                )
                span_provenance = derive_provenance(
                    parent_provenance,
                    cropped,
                    "bounded_retranscription_crop_v1",
                    {
                        "start_ms": start,
                        "end_ms": end,
                        "start_frame": start * 16,
                        "end_frame_exclusive": end * 16,
                        "channel_index": channel,
                        "source_channel_count": metadata["channels"],
                        "output_sample_rate": 16000,
                        "output_encoding": "pcm_s16le",
                    },
                    timeline,
                )
                source = cropped
                metadata = {
                    **metadata,
                    **inspect_pcm_wav(source),
                    "span_audio_sha256": file_sha256(source),
                    "audio_provenance": span_provenance,
                }
            lease.checkpoint()
            from services.inference_slot import (
                estimate_model_request_bytes,
                memory_admission,
            )

            required = estimate_model_request_bytes(
                Path(profile.model_dir) / name for name in profile.artifacts
            )
            memory_admission_receipt = memory_admission(required)
            if memory_admission_receipt["status"] != "admit":
                raise ASRFailure("resource_capacity_exceeded")
            adapter = adapter_factory(profile)
            if metadata["channels"] > 1:
                from services.asr.channels import transcribe_channels

                input_digest = metadata.get("working_sha256") or metadata["sha256"]

                def load_channel(channel, pcm_hash):
                    lease.checkpoint(force=True)
                    with store.transaction() as con:
                        saved = con.execute(
                            "SELECT * FROM asr_checkpoints WHERE job=? AND channel_index=?",
                            (job["id"], channel),
                        ).fetchone()
                    if saved is None:
                        return None
                    if (
                        saved["input_sha256"] != input_digest
                        or saved["profile_sha256"] != profile.sha256
                    ):
                        raise ASRFailure("asset_integrity_failure")
                    value = json.loads(saved["body"])
                    if (
                        content_sha256(value) != saved["sha256"]
                        or value.get("isolated_channel_pcm_sha256") != pcm_hash
                    ):
                        raise ASRFailure("asset_integrity_failure")
                    build_transcript(
                        value,
                        metadata,
                        job["encounter"],
                        job["upload"],
                        profile,
                        str(uuid4()),
                        0,
                    )
                    return value

                def save_channel(channel, value):
                    build_transcript(
                        value,
                        metadata,
                        job["encounter"],
                        job["upload"],
                        profile,
                        str(uuid4()),
                        0,
                    )
                    lease.checkpoint(force=True)
                    with store.transaction() as con:
                        current = con.execute(
                            "SELECT lease_token,status FROM jobs WHERE id=?",
                            (job["id"],),
                        ).fetchone()
                        if (
                            current["lease_token"] != token
                            or current["status"] != "running"
                            or not processing_allowed(con, job["encounter"])
                        ):
                            raise ASRFailure("worker_lease_lost")
                        con.execute(
                            "INSERT INTO asr_checkpoints VALUES (?,?,?,?,?,?,?,?)",
                            (
                                job["id"],
                                job["encounter"],
                                channel,
                                input_digest,
                                profile.sha256,
                                canonical_json(value),
                                content_sha256(value),
                                datetime.now(timezone.utc).isoformat(),
                            ),
                        )

                raw = transcribe_channels(
                    source,
                    metadata,
                    adapter,
                    lease.checkpoint,
                    load_channel,
                    save_channel,
                )
            else:
                raw = adapter.transcribe(source, metadata, lease.checkpoint)
            manifest_path = diarization_manifest or os.environ.get(
                "MED_TRANSCRIPT_DIARIZATION_MANIFEST"
            )
            if (
                manifest_path
                and metadata["channels"] == 1
                and not job["preview_only"]
                and not span_request
            ):
                from services.diarization import LocalDiarizationProvider

                diarization_provider = require_provider(
                    LocalDiarizationProvider(),
                    DiarizationProvider,
                    "diarization",
                )
                speaker_report = diarization_provider.diarize(
                    source,
                    json.loads(Path(manifest_path).read_text(encoding="utf-8")),
                    lease.checkpoint,
                )
            lease.checkpoint()
        except ProviderFailure as exc:
            error = exc.code
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
        current_tx = con.execute(
            "SELECT current_transcript FROM encounters WHERE id=?", (job["encounter"],)
        ).fetchone()[0]
        if current_tx != job["expected_transcript_id"]:
            status, error = "cancelled", "transcript_changed"
        elif not processing_allowed(con, job["encounter"]):
            status, error = "cancelled", "authorization_required"
        else:
            if error is None:
                version = con.execute(
                    "SELECT COALESCE(MAX(version),0)+1 FROM transcript_versions WHERE encounter=?",
                    (job["encounter"],),
                ).fetchone()[0]
                transcript_id = str(uuid4())
                try:
                    from services.asr.channels import build_channels

                    builder = (
                        build_channels
                        if isinstance(raw, dict) and "channel_outputs" in raw
                        else build_transcript
                    )
                    body = builder(
                        raw,
                        metadata,
                        job["encounter"],
                        job["upload"],
                        profile,
                        transcript_id,
                        version,
                    )
                    body["provenance"]["worker_timing"] = {
                        "wall_seconds": time.perf_counter() - work_started,
                        "lease_checkpoint_calls": lease.checkpoint_calls,
                        "lease_database_checks": lease.db_checkpoints,
                        "lease_checkpoint_seconds": lease.checkpoint_seconds,
                        "minimum_checkpoint_interval_seconds": 1.0,
                    }
                    if memory_admission_receipt is not None:
                        body["provenance"]["memory_admission"] = (
                            memory_admission_receipt
                        )
                    if speaker_report is not None:
                        from services.diarization import attach_speakers

                        body = attach_speakers(body, speaker_report)
                    if span_request:
                        from services.asr.retranscribe_span import retranscribe_span

                        text = " ".join(s["text"].strip() for s in body["segments"])
                        if not text:
                            raise ASRFailure("invalid_asr_output")
                        result = retranscribe_span(
                            audio_asset_id=job["upload"],
                            start_ms=span_request["start_ms"],
                            end_ms=span_request["end_ms"],
                            source_transcript_version=job["expected_transcript_id"],
                            candidate_text=text,
                        )
                        result.update(
                            transcript_sha256=span_request["transcript_sha256"],
                            profile_sha256=profile.sha256,
                            span_audio_sha256=metadata["span_audio_sha256"],
                            span_audio_provenance=metadata["audio_provenance"],
                            channel_index=span_request["channel_index"],
                            candidate_segments=[
                                {
                                    **s,
                                    "start_ms": s["start_ms"]
                                    + span_request["start_ms"],
                                    "end_ms": s["end_ms"] + span_request["start_ms"],
                                }
                                for s in body["segments"]
                            ],
                        )
                    elif job["preview_only"]:
                        offset = job["timeline_offset_ms"]
                        result = {
                            "status": "provisional_not_a_source_version",
                            "approvable": False,
                            "profile_sha256": profile.sha256,
                            "input_sha256": metadata["sha256"],
                            "provisional_segments": [
                                {
                                    **segment,
                                    "start_ms": segment["start_ms"] + offset,
                                    "end_ms": segment["end_ms"] + offset,
                                    "role": "unknown",
                                    "role_status": "unconfirmed",
                                }
                                for segment in body["segments"]
                            ],
                        }
                    else:
                        from services.domain_contracts import validate_record

                        validate_record("transcript", body)
                        digest = content_sha256(body)
                        con.execute(
                            "INSERT INTO transcript_versions VALUES (?,?,?,?,?,?,?,?)",
                            (
                                transcript_id,
                                job["encounter"],
                                job["upload"],
                                job["id"],
                                version,
                                digest,
                                canonical_json(body),
                                finished.isoformat(),
                            ),
                        )
                        con.execute(
                            "UPDATE encounters SET current_transcript=? WHERE id=?",
                            (transcript_id, job["encounter"]),
                        )
                        from services.encounter_state import Stage, advance_persisted

                        lifecycle = con.execute(
                            "SELECT stage FROM encounter_lifecycle WHERE encounter=?",
                            (job["encounter"],),
                        ).fetchone()
                        if lifecycle and lifecycle["stage"] == Stage.CREATED.value:
                            advance_persisted(con, job["encounter"], Stage.RECORDING)
                        advance_persisted(con, job["encounter"], Stage.TRANSCRIBED)
                        result = {
                            "transcript_version_id": transcript_id,
                            "sha256": digest,
                            "transcript_url": f"/v1/encounters/{job['encounter']}/transcripts/{transcript_id}",
                        }
                        if job["preview_session_id"]:
                            preview_row = con.execute(
                                """SELECT id,result FROM jobs WHERE encounter=? AND preview_session_id=?
                                AND profile_sha256=? AND preview_only=1 AND status='succeeded'
                                ORDER BY created_at DESC,id DESC LIMIT 1""",
                                (
                                    job["encounter"],
                                    job["preview_session_id"],
                                    profile.sha256,
                                ),
                            ).fetchone()
                            if preview_row and preview_row["result"]:
                                from services.asr.preview_divergence import (
                                    compare_preview_to_final,
                                )

                                diagnostic = compare_preview_to_final(
                                    json.loads(preview_row["result"]),
                                    {
                                        **body,
                                        **result,
                                        "profile_sha256": profile.sha256,
                                    },
                                )
                                result["preview_divergence"] = {
                                    "preview_job_id": preview_row["id"],
                                    **diagnostic,
                                }
                except ASRFailure as exc:
                    error = exc.code
            status = "failed" if error else "succeeded"
        con.execute(
            "INSERT OR IGNORE INTO job_attempts VALUES (?,?,?,?,?,?)",
            (
                job["id"],
                job["encounter"],
                current["attempts"],
                status,
                error,
                finished.isoformat(),
            ),
        )
        con.execute(
            """UPDATE jobs SET status=?,error_code=?,result=?,lease_token=NULL,
            lease_expires_at=NULL,updated_at=? WHERE id=?""",
            (
                status,
                error,
                json.dumps(result) if result else None,
                finished.isoformat(),
                job["id"],
            ),
        )
        owner = con.execute(
            "SELECT tenant FROM encounters WHERE id=?", (job["encounter"],)
        ).fetchone()
        append_audit(
            con,
            (
                str(uuid4()),
                owner["tenant"],
                "local_asr_worker",
                f"transcription_{status}",
                job["id"],
                finished.isoformat(),
            ),
        )
    return {"id": job["id"], "status": status}


def main():
    parser = argparse.ArgumentParser(
        description="Process one queued local ASR job; never downloads model artifacts"
    )
    parser.add_argument("--db", default="data/development.sqlite3")
    parser.add_argument("--assets", default=None)
    args = parser.parse_args()
    root = args.assets or default_asset_root(args.db)
    print(json.dumps(run_once(args.db, root) or {"status": "idle"}))


if __name__ == "__main__":
    main()
