"""Audio endpoints; original version-one contracts and guards preserved."""

import hashlib
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from fastapi import Depends, HTTPException, Request
from services.api.ingest import file_sha256
from services.api.contracts import Identity, IdempotencyKey, UploadInput
from services.api.router_context import ApiServices
from services.api.time_utils import now
from services.domain_contracts import validate_record


def register(app, services: ApiServices):
    database = services.database
    identity = services.identity
    encounter = services.encounter
    audit = services.audit
    replay = services.replay
    remember = services.remember
    require_processing = services.require_processing
    upload_row = services.upload_row
    require_live_upload = services.require_live_upload
    assets = services.assets

    @app.post("/v1/encounters/{encounter_id}/audio-uploads", status_code=201)
    def create_upload(
        encounter_id: UUID,
        body: UploadInput,
        idempotency_key: IdempotencyKey,
        actor: Identity = Depends(identity),
    ):
        resource, created = str(uuid4()), now()
        expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        with database() as con:
            encounter(con, encounter_id, actor)
            require_processing(con, encounter_id)
            scope, fingerprint, previous = replay(
                con,
                actor,
                f"upload:{encounter_id}",
                idempotency_key,
                body.model_dump(mode="json"),
            )
            if previous:
                return previous
            con.execute(
                "INSERT INTO uploads (id,encounter,expected_bytes,expected_sha256,status,created_at,expires_at,media_type) VALUES (?,?,?,?,?,?,?,?)",
                (
                    resource,
                    str(encounter_id),
                    body.bytes,
                    body.sha256,
                    "open",
                    created,
                    expires,
                    body.media_type,
                ),
            )
            response = {
                "id": resource,
                "status": "open",
                "expires_at": expires,
                "content_url": f"/v1/encounters/{encounter_id}/audio-uploads/{resource}/content",
            }
            remember(con, scope, fingerprint, response)
            audit(con, actor, "upload_created", resource)
        return response

    @app.get("/v1/encounters/{encounter_id}/audio-uploads/{upload_id}")
    def get_upload(
        encounter_id: UUID, upload_id: UUID, actor: Identity = Depends(identity)
    ):
        with database() as con:
            row = upload_row(con, encounter_id, upload_id, actor)
            audit(con, actor, "upload_read", str(upload_id))
            return {
                "id": row["id"],
                "status": row["status"],
                "expected_bytes": row["expected_bytes"],
                "received_bytes": row["received_bytes"],
                "stream_format": row["stream_format"],
                "stream_sealed": bool(row["stream_sealed"]),
                "expires_at": row["expires_at"],
                "expired": datetime.fromisoformat(row["expires_at"])
                <= datetime.now(timezone.utc),
            }

    @app.put("/v1/encounters/{encounter_id}/audio-uploads/{upload_id}/content")
    async def upload_content(
        encounter_id: UUID,
        upload_id: UUID,
        request: Request,
        actor: Identity = Depends(identity),
    ):
        with database() as con:
            row = upload_row(con, encounter_id, upload_id, actor)
            require_processing(con, encounter_id)
            require_live_upload(row)
            if row["status"] != "open" or row["received_bytes"] or row["stream_format"]:
                raise HTTPException(409, "upload_not_open")
            if (
                request.headers.get("content-type", "").split(";")[0].strip().lower()
                != row["media_type"]
            ):
                raise HTTPException(415, "unsupported_media")
            con.execute(
                "UPDATE uploads SET status='uploading' WHERE id=?", (str(upload_id),)
            )

        temporary = assets / f"{upload_id}.{uuid4()}.part"
        destination = assets / f"{upload_id}.wav"
        digest, received = hashlib.sha256(), 0
        published = False
        try:
            with temporary.open("xb") as target:
                async for chunk in request.stream():
                    received += len(chunk)
                    if received > row["expected_bytes"]:
                        raise HTTPException(413, "upload_size_exceeded")
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            if (
                received != row["expected_bytes"]
                or digest.hexdigest() != row["expected_sha256"]
            ):
                raise HTTPException(422, "upload_integrity_failure")
            with database() as con:
                current = upload_row(con, encounter_id, upload_id, actor)
                require_live_upload(current)
                require_processing(con, encounter_id)
                os.replace(temporary, destination)
                con.execute(
                    "UPDATE uploads SET status='uploaded',received_bytes=? WHERE id=?",
                    (received, str(upload_id)),
                )
                audit(con, actor, "upload_received", str(upload_id))
            published = True
        except OSError:
            raise HTTPException(503, "asset_storage_unavailable") from None
        finally:
            temporary.unlink(missing_ok=True)
            if not published:
                with database() as con:
                    destination.unlink(missing_ok=True)
                    con.execute(
                        "UPDATE uploads SET status='open' WHERE id=? AND status='uploading'",
                        (str(upload_id),),
                    )
        return {
            "id": str(upload_id),
            "status": "uploaded",
            "bytes": received,
            "sha256": digest.hexdigest(),
        }

    @app.post(
        "/v1/encounters/{encounter_id}/audio-uploads/{upload_id}/complete",
        status_code=202,
    )
    def complete_upload(
        encounter_id: UUID, upload_id: UUID, actor: Identity = Depends(identity)
    ):
        with database() as con:
            row = upload_row(con, encounter_id, upload_id, actor)
            require_processing(con, encounter_id)
            existing = con.execute(
                "SELECT id FROM jobs WHERE upload=? AND stage='audio_ingest'",
                (str(upload_id),),
            ).fetchone()
            if existing:
                return {
                    "job_id": existing["id"],
                    "status_url": f"/v1/jobs/{existing['id']}",
                }
            require_live_upload(row)
            if row["stream_format"] and not row["stream_sealed"]:
                raise HTTPException(409, "live_upload_requires_seal")
            if row["status"] != "uploaded":
                raise HTTPException(409, "upload_not_received")
            try:
                source = assets / f"{upload_id}.wav"
                if (
                    source.stat().st_size != row["expected_bytes"]
                    or file_sha256(source) != row["expected_sha256"]
                ):
                    raise HTTPException(422, "upload_integrity_failure")
            except OSError:
                raise HTTPException(503, "asset_storage_unavailable") from None
            try:
                validate_record(
                    "audio_source",
                    {
                        "id": str(upload_id),
                        "encounter_id": str(encounter_id),
                        "sha256": row["expected_sha256"],
                        "byte_count": row["expected_bytes"],
                        "media_type": row["media_type"],
                        "state": "sealed",
                    },
                )
            except ValueError:
                raise HTTPException(422, "audio_source_metadata_invalid") from None
            job_id, created = str(uuid4()), now()
            con.execute(
                """INSERT INTO jobs (id, upload, encounter, status, created_at, updated_at)
                VALUES (?,?,?,'queued',?,?)""",
                (job_id, str(upload_id), str(encounter_id), created, created),
            )
            con.execute(
                "UPDATE uploads SET status='complete' WHERE id=?", (str(upload_id),)
            )
            audit(con, actor, "ingest_queued", job_id)
        return {"job_id": job_id, "status_url": f"/v1/jobs/{job_id}"}
