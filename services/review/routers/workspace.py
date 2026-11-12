"""Workspace routes with preserved exact-version review contracts."""

from services.audit_integrity import approval_body
from services.api.job_state import progress as job_progress, retryable as job_retryable
import json
from pathlib import Path
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, Query
from fastapi.responses import FileResponse

from services.asr.profiles import canonical_json


from services.review.service import ReviewService
from services.review.engine import current_safety_recheck


def register(app, services: ReviewService):
    database = services.database
    identity = services.identity
    audit = services.audit
    assets = services.assets
    profiles = services.profiles
    stamp = services.stamp
    get_tx = services.get_tx
    document = services.document
    current = services.current
    store_tx = services.store_tx

    @app.get("/v1/study-dashboard")
    def study_dashboard(actor=Depends(identity)):
        from services.review.presentation import campaign_evidence

        root = Path(__file__).resolve().parents[3] / "evaluation" / "reports"
        return campaign_evidence(root)

    @app.get("/v1/session")
    def session(actor=Depends(identity)):
        return {
            "clinician_id": str(actor.clinician_id),
            "tenant_id": str(actor.tenant_id),
            "role": actor.role,
            "data_mode": "synthetic_only",
            "asr_profiles": list(profiles),
            "demo_available": (assets.parent / "demo-sample.json").is_file(),
            "clinical_models_enabled": bool(app.state.clinical_models.enabled),
        }

    @app.get("/v1/demo-cases")
    def demo_cases(actor=Depends(identity)):
        from services.review.presentation import public_demo_cases

        return {
            "items": [
                {
                    "id": c["group_id"],
                    "duration_ms": c["duration_ms"],
                    "attribution": c["attribution"],
                }
                for c in public_demo_cases()
            ],
            "scope": "Public mock consultation development references, not ASR output or independent acceptance.",
        }

    @app.post("/v1/demo", status_code=201)
    def demo(
        public_case: str | None = Query(default=None, max_length=100),
        actor=Depends(identity),
    ):
        from services.api.ingest import file_sha256, inspect_pcm_wav
        import shutil

        bundle_path = assets.parent / "demo-sample.json"
        source = assets.parent / "demo-sample.wav"
        if public_case is not None:
            from services.review.presentation import public_demo

            try:
                source, bundle = public_demo(public_case)
            except (ValueError, OSError):
                raise HTTPException(
                    422, "public_demo_unavailable_or_integrity_failure"
                ) from None
        else:
            if not bundle_path.is_file() or not source.is_file():
                raise HTTPException(503, "synthetic_example_not_installed")
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        metadata = inspect_pcm_wav(source)
        digest = file_sha256(source)
        eid, uid, jid, created = str(uuid4()), str(uuid4()), str(uuid4()), stamp()
        body = {
            "patient_reference_id": str(uuid4()),
            "patient_identifiers_confirmed": True,
            "language": "en",
            "timezone": "Asia/Kolkata",
            "workflow": "outpatient_general_medicine",
            "requested_inference_mode": "fully_local",
            "synthetic_data": True,
        }
        destination = assets / f"{uid}.wav"
        shutil.copyfile(source, destination)
        try:
            with database() as con:
                con.execute(
                    "INSERT INTO encounters (id,tenant,clinician,body,created_at) VALUES (?,?,?,?,?)",
                    (
                        eid,
                        str(actor.tenant_id),
                        str(actor.clinician_id),
                        canonical_json(body),
                        created,
                    ),
                )
                con.execute(
                    "INSERT INTO authorizations VALUES (?,?,?,?,NULL)",
                    (
                        str(uuid4()),
                        eid,
                        canonical_json(
                            {
                                "scopes": ["recording", "local_processing"],
                                "method": "written",
                                "policy_version": "synthetic-example-v1",
                                "expires_at": datetime.fromtimestamp(
                                    datetime.now(timezone.utc).timestamp() + 8 * 3600,
                                    timezone.utc,
                                ).isoformat(),
                            }
                        ),
                        created,
                    ),
                )
                con.execute(
                    "INSERT INTO uploads (id,encounter,expected_bytes,expected_sha256,status,created_at,expires_at) VALUES (?,?,?,?,?,?,?)",
                    (
                        uid,
                        eid,
                        source.stat().st_size,
                        digest,
                        "complete",
                        created,
                        created,
                    ),
                )
                metadata["sha256"] = digest
                con.execute(
                    "INSERT INTO jobs (id,upload,encounter,status,created_at,updated_at,result) VALUES (?,?,?,'succeeded',?,?,?)",
                    (jid, uid, eid, created, created, canonical_json(metadata)),
                )
                segments = [
                    {
                        **segment,
                        "segment_id": str(uuid4()),
                        "speaker_id": None,
                        "role_status": "public_reference_annotation_requires_review"
                        if public_case
                        else "synthetic_reference_annotation",
                        "alignment_status": "fixture_audio_boundaries",
                        "language": "en",
                        "language_status": "uncertain",
                        "uncertainties": ["clinician_review_required"],
                    }
                    for segment in bundle["segments"]
                ]
                tx = {
                    "schema_version": "1.0",
                    "audio_asset_id": uid,
                    "input_sha256": digest,
                    "duration_ms": metadata["duration_ms"],
                    "segments": segments,
                    "status": "review_required",
                    "source_availability": "available",
                    "review": {},
                    "provenance": {
                        "engine": "public_human_reference_not_asr"
                        if public_case
                        else "synthetic_reference_transcript",
                        "fixture_id": public_case
                        or bundle.get("fixture_id", "outpatient_english_v1"),
                        "attribution": bundle.get(
                            "attribution", "Synthetic scripted example"
                        ),
                        "independent_clinical_gold": False,
                        "limitations": bundle.get(
                            "limitations",
                            "Reference annotations require review; not independent clinical acceptance.",
                        ),
                    },
                    "untranscribed_intervals": [],
                    "review_flags": [
                        "clinician_review_required",
                        "language_support_unverified",
                    ],
                }
                store_tx(con, eid, uid, tx, actor)
                audit(con, actor, "synthetic_example_created", eid)
            return {"encounter_id": eid}
        except BaseException:
            destination.unlink(missing_ok=True)
            raise

    @app.get("/v1/encounters/{eid}/uploads")
    def uploads(eid: UUID, actor=Depends(identity)):
        with database() as con:
            current(con, eid, actor)
            rows = con.execute(
                """SELECT uploads.id,uploads.status,uploads.expected_bytes,jobs.id AS ingest_job_id
                FROM uploads LEFT JOIN jobs ON jobs.upload=uploads.id AND jobs.stage='audio_ingest'
                WHERE uploads.encounter=? ORDER BY uploads.created_at DESC LIMIT 100""",
                (str(eid),),
            ).fetchall()
            return {"items": [dict(row) for row in rows]}

    @app.get("/v1/encounters")
    def list_encounters(
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0, le=10000),
        actor=Depends(identity),
    ):
        with database() as con:
            rows = con.execute(
                """SELECT * FROM encounters WHERE tenant=? AND clinician=? AND deleted_at IS NULL
                ORDER BY created_at DESC,id LIMIT ? OFFSET ?""",
                (str(actor.tenant_id), str(actor.clinician_id), limit, offset),
            ).fetchall()
            return {
                "items": [
                    {
                        "id": row["id"],
                        "created_at": row["created_at"],
                        "patient_reference_id": json.loads(row["body"])[
                            "patient_reference_id"
                        ],
                        "current_transcript_id": row["current_transcript"],
                        "current_note_id": row["current_note"],
                    }
                    for row in rows
                ],
                "next_offset": offset + limit if len(rows) == limit else None,
            }

    @app.get("/v1/encounters/{eid}/workspace")
    def workspace(eid: UUID, actor=Depends(identity)):
        with database() as con:
            row = current(con, eid, actor)
            tx = note = report = approval = recheck = None
            if row["current_transcript"]:
                tr, tx = get_tx(con, eid, row["current_transcript"])
                tx = {**tx, "sha256": tr["sha256"]}
            if row["current_note"]:
                nr, note = document(con, eid, row["current_note"])
                note = {**note, "sha256": nr["sha256"]}
                _, report = document(
                    con, eid, note["verification_report_id"], "verification"
                )
                ar = con.execute(
                    "SELECT * FROM approvals WHERE note=?", (note["id"],)
                ).fetchone()
                approval = approval_body(con, ar) if ar else None
                _, saved_source = get_tx(con, eid, note["transcript_version_id"])
                recheck = current_safety_recheck(note, saved_source, report)
            jobs = con.execute(
                "SELECT id,stage,status,error_code,result,attempts,upload,preview_only FROM jobs WHERE encounter=? ORDER BY created_at DESC LIMIT 20",
                (str(eid),),
            ).fetchall()
            return {
                "encounter": {"id": str(eid), **json.loads(row["body"])},
                "transcript": tx,
                "note": note,
                "verification": report,
                "approval": approval,
                "current_safety_recheck": recheck,
                "stale": bool(
                    note and (not tx or note["transcript_version_id"] != tx["id"])
                ),
                "jobs": [
                    {
                        **dict(job),
                        "retryable": job_retryable(job),
                        "progress": job_progress(con, job)
                        if job["status"] in ("queued", "running", "failed")
                        else None,
                        "result": json.loads(job["result"]) if job["result"] else None,
                    }
                    for job in jobs
                ],
                "exports": [
                    dict(item)
                    for item in con.execute(
                        "SELECT id,format,sha256,created_at FROM exports WHERE encounter=?",
                        (str(eid),),
                    )
                ],
            }

    @app.get("/v1/encounters/{eid}/audio/{upload_id}")
    def audio(
        eid: UUID,
        upload_id: UUID,
        channel: int | None = Query(default=None, ge=0, le=7),
        actor=Depends(identity),
    ):
        with database() as con:
            current(con, eid, actor)
            row = con.execute(
                "SELECT * FROM uploads WHERE id=? AND encounter=? AND status='complete'",
                (str(upload_id), str(eid)),
            ).fetchone()
            path = assets / f"{upload_id}.wav"
            if not row or not path.is_file():
                raise HTTPException(404, "audio_unavailable")
            audit(con, actor, "audio_playback", str(upload_id))
        if channel is not None:
            import tempfile
            from starlette.background import BackgroundTask
            from services.api.ingest import file_sha256, inspect_pcm_wav
            from services.asr.channels import write_channel

            with database() as con:
                ingest = con.execute(
                    "SELECT result FROM jobs WHERE upload=? AND encounter=? AND stage='audio_ingest' AND status='succeeded'",
                    (str(upload_id), str(eid)),
                ).fetchone()
            if not ingest:
                raise HTTPException(409, "audio_ingest_required")
            metadata = json.loads(ingest["result"])
            if metadata.get("working_filename"):
                path = assets / f"{upload_id}.normalized.wav"
            expected = metadata.get("working_sha256") or row["expected_sha256"]
            if not path.is_file() or file_sha256(path) != expected:
                raise HTTPException(409, "asset_integrity_failure")
            if channel >= inspect_pcm_wav(path)["channels"]:
                raise HTTPException(422, "channel_unavailable")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                isolated = Path(handle.name)
            try:
                write_channel(path, isolated, channel)
            except Exception:
                isolated.unlink(missing_ok=True)
                raise
            return FileResponse(
                isolated,
                media_type="audio/wav",
                background=BackgroundTask(isolated.unlink, missing_ok=True),
            )
        return FileResponse(path, media_type=row["media_type"])

    @app.get("/v1/encounters/{eid}/audio/{upload_id}/waveform")
    def audio_waveform(
        eid: UUID,
        upload_id: UUID,
        channel: int | None = Query(default=None, ge=0, le=7),
        actor=Depends(identity),
    ):
        from services.audio_waveform import waveform

        with database() as con:
            current(con, eid, actor)
            upload = con.execute(
                "SELECT * FROM uploads WHERE id=? AND encounter=? AND status='complete'",
                (str(upload_id), str(eid)),
            ).fetchone()
            ingest = con.execute(
                "SELECT result FROM jobs WHERE upload=? AND encounter=? AND stage='audio_ingest' AND status='succeeded'",
                (str(upload_id), str(eid)),
            ).fetchone()
            if upload is None or ingest is None:
                raise HTTPException(404, "audio_unavailable")
            metadata = json.loads(ingest["result"])
            filename = metadata.get("working_filename")
            if filename is not None and Path(filename).name != filename:
                raise HTTPException(409, "asset_integrity_failure")
            path = assets / filename if filename else assets / f"{upload_id}.wav"
            expected = metadata.get("working_sha256") or upload["expected_sha256"]
            audit(con, actor, "audio_waveform_read", str(upload_id))
        if not path.is_file():
            raise HTTPException(404, "audio_unavailable")
        try:
            return waveform(path, expected, channel)
        except ValueError as exc:
            code = str(exc)
            if code == "channel_unavailable":
                raise HTTPException(422, code) from None
            raise HTTPException(409, "asset_integrity_failure") from None
