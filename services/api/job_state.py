"""Scoped callers use this for nonclinical progress and retry metadata."""

import json
import os


DEFAULT_PENDING_TRANSCRIPTION_LIMIT = 16
MAX_PENDING_TRANSCRIPTION_LIMIT = 256


def pending_transcription_capacity(con, tenant_id):
    """Return a generic capacity decision without exposing tenant queue depth."""
    configured = os.environ.get("MED_TRANSCRIPT_MAX_PENDING_ASR_JOBS")
    try:
        limit = (
            int(configured)
            if configured is not None
            else DEFAULT_PENDING_TRANSCRIPTION_LIMIT
        )
    except ValueError:
        return False
    if not 1 <= limit <= MAX_PENDING_TRANSCRIPTION_LIMIT:
        return False
    pending = con.execute(
        """SELECT COUNT(*) FROM jobs JOIN encounters ON encounters.id=jobs.encounter
        WHERE encounters.tenant=? AND jobs.stage='transcription'
        AND jobs.status IN ('queued','running')""",
        (str(tenant_id),),
    ).fetchone()[0]
    return pending < limit


def request_cancellation(con, job_id, updated_at):
    """Cancel queued/running work; active workers stop at their next checkpoint."""
    row = con.execute("SELECT status FROM jobs WHERE id=?", (str(job_id),)).fetchone()
    if row is None:
        return None
    if row["status"] in {"queued", "running"}:
        con.execute(
            """UPDATE jobs SET status='cancelled',error_code='cancelled_by_user',
            lease_token=NULL,lease_expires_at=NULL,updated_at=?
            WHERE id=? AND status IN ('queued','running')""",
            (updated_at, str(job_id)),
        )
    current = con.execute(
        "SELECT status FROM jobs WHERE id=?", (str(job_id),)
    ).fetchone()
    return current["status"] if current else None


def retryable(row):
    return (
        row["stage"] == "transcription"
        and row["status"] == "failed"
        and row["attempts"] < 3
        and row["error_code"]
        in {"asr_failed", "worker_lease_lost", "asset_unavailable"}
    )


def progress(con, row):
    if row["stage"] != "transcription":
        return None
    ingest = con.execute(
        "SELECT result FROM jobs WHERE upload=? AND stage='audio_ingest' AND status='succeeded'",
        (row["upload"],),
    ).fetchone()
    metadata = json.loads(ingest["result"]) if ingest else {}
    completed = con.execute(
        "SELECT COUNT(*) FROM asr_checkpoints WHERE job=?", (row["id"],)
    ).fetchone()[0]
    return {
        "completed_channels": completed,
        "total_channels": metadata.get("asr_channels", metadata.get("channels", 0)),
        "partial_output_is_not_a_source_version": True,
    }
