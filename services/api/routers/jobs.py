"""Jobs endpoints; original version-one contracts and guards preserved."""

import json
from uuid import UUID, uuid4
from fastapi import Depends, HTTPException
from services.api.ingest import MAX_CHANNELS
from services.api.contracts import Identity, IdempotencyKey, TranscriptionInput
from services.api.router_context import ApiServices
from services.api.time_utils import now
from services.api.job_state import progress as job_progress, retryable as job_retryable
from services.api.idempotency import idempotent


def register(app, services: ApiServices):
    database = services.database
    identity = services.identity
    encounter = services.encounter
    audit = services.audit
    replay = services.replay
    remember = services.remember
    require_processing = services.require_processing
    upload_row = services.upload_row
    profiles = services.profiles

    @app.get("/v1/jobs/{job_id}")
    def get_job(job_id: UUID, actor: Identity = Depends(identity)):
        with database() as con:
            row = con.execute(
                """SELECT jobs.* FROM jobs JOIN encounters ON encounters.id=jobs.encounter
                WHERE jobs.id=? AND encounters.tenant=? AND encounters.clinician=?""",
                (str(job_id), str(actor.tenant_id), str(actor.clinician_id)),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "job_not_found")
            audit(con, actor, "job_read", str(job_id))
            return {
                "id": row["id"],
                "encounter_id": row["encounter"],
                "stage": row["stage"],
                "profile_sha256": row["profile_sha256"],
                "status": row["status"],
                "attempts": row["attempts"],
                "error_code": row["error_code"],
                "retryable": job_retryable(row),
                "preview_only": bool(row["preview_only"]),
                "preview_session_id": row["preview_session_id"],
                "progress": job_progress(con, row),
                "attempt_history": [
                    dict(r)
                    for r in con.execute(
                        "SELECT attempt,status,error_code,finished_at FROM job_attempts WHERE job=? ORDER BY attempt",
                        (str(job_id),),
                    )
                ],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "result": json.loads(row["result"]) if row["result"] else None,
            }

    @app.post("/v1/jobs/{job_id}/retry", status_code=202)
    @idempotent(database, replay, "POST:/v1/jobs/{job_id}/retry")
    def retry_transcription(
        job_id: UUID,
        idempotency_key: IdempotencyKey,
        actor: Identity = Depends(identity),
    ):
        with database() as con:
            job = con.execute(
                "SELECT * FROM jobs WHERE id=?", (str(job_id),)
            ).fetchone()
            if job is None:
                raise HTTPException(404, "job_not_found")
            owner = encounter(con, job["encounter"], actor)
            require_processing(con, job["encounter"])
            if (
                job["stage"] != "transcription"
                or job["status"] != "failed"
                or job["attempts"] >= 3
                or job["error_code"]
                not in {"asr_failed", "worker_lease_lost", "asset_unavailable"}
            ):
                raise HTTPException(409, "job_not_retryable")
            if owner["current_transcript"] != job["expected_transcript_id"]:
                raise HTTPException(412, "stale_transcript")
            con.execute(
                "UPDATE jobs SET status='queued',error_code=NULL,result=NULL,updated_at=? WHERE id=?",
                (now(), str(job_id)),
            )
            audit(con, actor, "transcription_retry_queued", str(job_id))
            return {"job_id": str(job_id), "status_url": f"/v1/jobs/{job_id}"}

    @app.post("/v1/encounters/{encounter_id}/transcriptions", status_code=202)
    @idempotent(database, replay, "POST:/v1/encounters/{encounter_id}/transcriptions")
    def create_transcription(
        encounter_id: UUID,
        body: TranscriptionInput,
        idempotency_key: IdempotencyKey,
        actor: Identity = Depends(identity),
    ):
        with database() as con:
            encounter(con, encounter_id, actor)
            require_processing(con, encounter_id)
            scope, fingerprint, previous = replay(
                con,
                actor,
                f"transcription:{encounter_id}",
                idempotency_key,
                body.model_dump(mode="json"),
            )
            if previous:
                return previous
            profile = profiles.get(body.inference_profile_id)
            if profile is None:
                raise HTTPException(503, "asr_profile_unavailable")
            upload = upload_row(con, encounter_id, body.audio_asset_id, actor)
            ingest = con.execute(
                "SELECT * FROM jobs WHERE upload=? AND stage='audio_ingest'",
                (upload["id"],),
            ).fetchone()
            if ingest is None or ingest["status"] != "succeeded":
                raise HTTPException(409, "audio_ingest_required")
            metadata = json.loads(ingest["result"])
            if (
                metadata.get("asr_sample_rate", metadata["sample_rate"]) != 16000
                or not 1
                <= metadata.get("asr_channels", metadata["channels"])
                <= MAX_CHANNELS
            ):
                raise HTTPException(422, "unsupported_asr_input")
            if body.preview_only:
                duration = metadata.get(
                    "normalized_duration_ms", metadata["duration_ms"]
                )
                if duration > 15000 or duration + body.timeline_offset_ms > 3600000:
                    raise HTTPException(422, "preview_window_limit_exceeded")
                if con.execute(
                    "SELECT 1 FROM jobs WHERE encounter=? AND preview_only=1 AND status IN ('queued','running')",
                    (str(encounter_id),),
                ).fetchone():
                    raise HTTPException(409, "preview_already_pending")
            elif body.timeline_offset_ms:
                raise HTTPException(422, "offset_requires_preview_mode")
            existing = con.execute(
                """SELECT id FROM jobs WHERE upload=? AND stage='transcription'
                AND profile_sha256=? AND retranscription IS NULL AND preview_only=?
                AND timeline_offset_ms=? AND COALESCE(preview_session_id,'')=COALESCE(?,'')""",
                (
                    upload["id"], profile.sha256, int(body.preview_only),
                    body.timeline_offset_ms,
                    str(body.preview_session_id) if body.preview_session_id else None,
                ),
            ).fetchone()
            job_id, created = existing["id"] if existing else str(uuid4()), now()
            if not existing:
                con.execute(
                    """INSERT INTO jobs (id,upload,encounter,status,created_at,updated_at,stage,profile_sha256,expected_transcript_id,preview_only,timeline_offset_ms,preview_session_id)
                    VALUES (?,?,?,'queued',?,?,'transcription',?,?,?,?,?)""",
                    (
                        job_id,
                        upload["id"],
                        str(encounter_id),
                        created,
                        created,
                        profile.sha256,
                        encounter(con, encounter_id, actor)["current_transcript"],
                        int(body.preview_only),
                        body.timeline_offset_ms,
                        str(body.preview_session_id) if body.preview_session_id else None,
                    ),
                )
                audit(con, actor, "transcription_queued", job_id)
            response = {"job_id": job_id, "status_url": f"/v1/jobs/{job_id}"}
            remember(con, scope, fingerprint, response)
        return response
