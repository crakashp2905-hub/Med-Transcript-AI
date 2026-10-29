import hashlib
from contextlib import nullcontext
from services.inference_slot import local_inference_slot
from services.api.job_state import progress as job_progress,retryable as job_retryable
import json
from pathlib import Path
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response

from services.asr.profiles import canonical_json, content_sha256
from services.review.engine import findings_for, propose_facts, render_export, render_sections, validate_evidence
from services.review.models import (AmendmentInput, ApprovalInput, DraftInput, ExportInput, ManualTranscript,
                                    NoteEdit, ResolutionInput, TranscriptEdit, SpeakerRoleConfirmation)


def register_review_routes(app, database, identity, encounter, audit, require_processing, assets, profiles):
    from services.review.providers import configured_provider, JSONProvider, DeterministicProvider
    from services.review.models import DraftProposalInput
    app.state.drafting_provider = configured_provider()

    @app.get('/v1/study-dashboard')
    def study_dashboard(actor=Depends(identity)):
        root = Path(__file__).resolve().parents[2] / 'evaluation' / 'reports'
        reports = {}
        for key, filename in (
            ('ranking', 'detailed-ranking-v2-2026-10-29.json'),
            ('drafting', 'detailed-drafting-summary-2026-10-29.json'),
            ('execution', 'detailed-campaign-execution-receipt-2026-10-29.json'),
        ):
            try:
                reports[key] = json.loads((root / filename).read_text(encoding='utf-8'))
            except (OSError, ValueError):
                reports[key] = None
        return {'reports': reports, 'clinical_validation': False,
                'scope': 'public synthetic development evidence; not independent clinical acceptance',
                'provider_cost': 0, 'hardware_cost': None}

    @app.get("/v1/encounters/{eid}/draft-proposals/{did}")
    def get_draft_proposal(eid: UUID, did: UUID, actor=Depends(identity)):
        with database() as con:
            row = encounter(con,eid,actor)
            proposal = con.execute("SELECT body FROM model_proposals WHERE encounter=? AND id=? AND kind='draft_proposal'",(str(eid),str(did))).fetchone()
            if proposal is None:
                raise HTTPException(404,"draft_proposal_not_found")
            value = json.loads(proposal["body"])
            value["stale"] = row["current_transcript"] != value["transcript_version_id"]
            return value

    @app.post("/v1/encounters/{eid}/draft-proposals", status_code=201)
    def draft_proposal(eid: UUID, body: DraftProposalInput, actor=Depends(identity)):
        from services.api.storage import active_scopes
        provider = app.state.drafting_provider
        hosted = isinstance(provider, JSONProvider) and provider.mode == "hosted"
        with database() as con:
            row = encounter(con, eid, actor)
            require_processing(con, eid)
            if row["current_transcript"] != str(body.transcript_version_id):
                raise HTTPException(412, "stale_transcript")
            tr, tx = get_tx(con, eid, body.transcript_version_id)
            validate_evidence(body.facts, tx)
            original_hash = tr["sha256"]
            if hosted and (not body.hosted_text_disclosure_accepted or json.loads(row["body"])["requested_inference_mode"] != "hybrid_text" or "hosted_text_processing" not in active_scopes(con,eid)):
                raise HTTPException(422, "hosted_text_disclosure_and_scope_required")
        try:
            with (local_inference_slot() if isinstance(provider,JSONProvider) and provider.mode=='local' else nullcontext(True)) as ready:
                if not ready:raise HTTPException(503,'local_inference_busy')
                result = provider.draft([f.model_dump(mode="json") for f in body.facts], authorized=True, synthetic=True)
            result['deterministic_baseline'] = DeterministicProvider().draft(
                [f.model_dump(mode='json') for f in body.facts], authorized=True, synthetic=True)
        except ValueError:
            raise HTTPException(422, "draft_proposal_failed_no_output_admitted") from None
        with database() as con:
            row = encounter(con, eid, actor)
            require_processing(con, eid)
            if hosted and "hosted_text_processing" not in active_scopes(con,eid):
                raise HTTPException(403, "hosted_text_authorization_withdrawn")
            tr, _ = get_tx(con, eid, body.transcript_version_id)
            if row["current_transcript"] != str(body.transcript_version_id) or tr["sha256"] != original_hash:
                raise HTTPException(412, "stale_transcript")
            did, created = str(uuid4()), stamp()
            version = con.execute("SELECT COALESCE(MAX(version),0)+1 FROM model_proposals WHERE encounter=? AND kind='draft_proposal'", (str(eid),)).fetchone()[0]
            result.update(id=did, transcript_version_id=str(body.transcript_version_id), transcript_sha256=original_hash,
                source_facts=[f.model_dump(mode="json") for f in body.facts], status="unreviewed_proposal_not_approvable")
            con.execute("INSERT INTO model_proposals VALUES (?,?,?,?,?,?,?)", (did,str(eid),"draft_proposal",version,content_sha256(result),canonical_json(result),created))
            audit(con, actor, "draft_proposal_created", did)
            return result

    def stamp():
        return datetime.now(timezone.utc).isoformat()

    def get_tx(con, eid, tid):
        row = con.execute("SELECT * FROM transcript_versions WHERE encounter=? AND id=?", (str(eid), str(tid))).fetchone()
        if row is None:
            raise HTTPException(404, "transcript_not_found")
        return row, json.loads(row["body"])

    def document(con, eid, did, kind="note"):
        row = con.execute("SELECT * FROM documents WHERE encounter=? AND id=? AND kind=?", (str(eid), str(did), kind)).fetchone()
        if row is None:
            raise HTTPException(404, "document_not_found")
        return row, json.loads(row["body"])

    from services.review.metrics_routes import register as register_metrics
    register_metrics(app,database,identity,encounter,require_processing,document,audit)
    from services.review.clinical_routes import register as register_clinical
    register_clinical(app,database,identity,encounter,require_processing,get_tx,document,audit)

    @app.get('/v1/encounters/{eid}/versions')
    def versions(eid: UUID,actor=Depends(identity)):
        with database() as con:
            encounter(con,eid,actor)
            return {'notes':[dict(r) for r in con.execute("SELECT id,version,sha256,created_at FROM documents WHERE encounter=? AND kind='note' ORDER BY version DESC LIMIT 100",(str(eid),))],
                'transcripts':[dict(r) for r in con.execute('SELECT id,version,sha256,created_at FROM transcript_versions WHERE encounter=? ORDER BY version DESC LIMIT 100',(str(eid),))],'limit':100}

    @app.get('/v1/encounters/{eid}/notes/{before}/compare/{after}')
    def compare_notes(eid: UUID,before: UUID,after: UUID,actor=Depends(identity)):
        from services.review.comparison import compare
        with database() as con:
            encounter(con,eid,actor)
            _,a=document(con,eid,before)
            _,b=document(con,eid,after)
            return compare(a,b)

    def current(con, eid, actor):
        return encounter(con, eid, actor)

    def if_current(row, field, resource, sha, etag):
        if row[field] != str(resource) or etag != f'"{sha}"':
            raise HTTPException(412, "version_changed_reload_required")

    def store_tx(con, eid, upload, body, actor, parent=None):
        tid = str(uuid4())
        version = con.execute("SELECT COALESCE(MAX(version),0)+1 FROM transcript_versions WHERE encounter=?", (str(eid),)).fetchone()[0]
        body.update(id=tid, version=version, encounter_id=str(eid), parent_version_id=parent,
                    creator=str(actor.clinician_id), created_at=stamp())
        digest = content_sha256(body)
        con.execute("INSERT INTO transcript_versions VALUES (?,?,?,?,?,?,?,?)",
                    (tid, str(eid), upload, None, version, digest, canonical_json(body), stamp()))
        con.execute("UPDATE encounters SET current_transcript=? WHERE id=?", (tid, str(eid)))
        audit(con, actor, "transcript_version_created", tid)
        return {**body, "sha256": digest}

    def save_note(con, eid, tx_row, tx, facts, actor, parent=None, amendment_reason=""):
        validate_evidence(facts, tx)
        version = con.execute("SELECT COALESCE(MAX(version),0)+1 FROM documents WHERE encounter=? AND kind='note'", (str(eid),)).fetchone()[0]
        nid, rid, created = str(uuid4()), str(uuid4()), stamp()
        values = [fact.model_dump(mode="json") for fact in facts]
        for value in values:
            value["review_actor"] = str(actor.clinician_id) if value["reviewed"] else None
            value["reviewed_at"] = created if value["reviewed"] else None
        body = {"schema_version": "1.0", "id": nid, "version": version, "encounter_id": str(eid),
                "parent_version_id": parent, "transcript_version_id": tx_row["id"],
                "transcript_sha256": tx_row["sha256"], "facts": values, "sections": render_sections(values),
                "verification_report_id": rid, "creator": str(actor.clinician_id), "created_at": created,
                "amendment_reason": amendment_reason, "template_id": "reviewed_facts_soap_v1",
                "status": "review_required", "provenance": {"engine": "deterministic_reviewed_facts_template_v1"}}
        digest = content_sha256(body)
        findings = findings_for(body, tx)
        report = {"schema_version": "1.0", "id": rid, "note_version_id": nid, "note_sha256": digest,
                  "transcript_version_id": tx_row["id"], "transcript_sha256": tx_row["sha256"],
                  "validator_version": "rules_v2", "findings": findings, "gate": "blocked" if findings else "ready",
                  "created_at": created}
        con.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?)",
                    (nid, str(eid), "note", version, digest, canonical_json(body), created))
        con.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?)",
                    (rid, str(eid), "verification", version, content_sha256(report), canonical_json(report), created))
        con.execute("UPDATE encounters SET current_note=? WHERE id=?", (nid, str(eid)))
        audit(con, actor, "note_version_created", nid)
        return {"note": {**body, "sha256": digest}, "verification": report}

    @app.get("/v1/session")
    def session(actor=Depends(identity)):
        return {"clinician_id": str(actor.clinician_id), "tenant_id": str(actor.tenant_id),
                "data_mode": "synthetic_only", "asr_profiles": list(profiles),
                "demo_available": (assets.parent / "demo-sample.json").is_file(),
                "clinical_models_enabled": bool(app.state.clinical_models.enabled)}

    @app.get('/v1/demo-cases')
    def demo_cases(actor=Depends(identity)):
        from services.review.presentation import public_demo_cases
        return {'items': [{'id': c['group_id'], 'duration_ms': c['duration_ms'], 'attribution': c['attribution']} for c in public_demo_cases()],
                'scope': 'Public mock consultation development references, not ASR output or independent acceptance.'}

    @app.post("/v1/demo", status_code=201)
    def demo(public_case: str | None = Query(default=None, max_length=100), actor=Depends(identity)):
        from services.api.ingest import file_sha256, inspect_pcm_wav
        import shutil
        bundle_path = assets.parent / "demo-sample.json"
        source = assets.parent / "demo-sample.wav"
        if public_case is not None:
            from services.review.presentation import public_demo
            try:
                source, bundle = public_demo(public_case)
            except (ValueError, OSError):
                raise HTTPException(422, 'public_demo_unavailable_or_integrity_failure') from None
        else:
            if not bundle_path.is_file() or not source.is_file():
                raise HTTPException(503, "synthetic_example_not_installed")
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        metadata = inspect_pcm_wav(source)
        digest = file_sha256(source)
        eid, uid, jid, created = str(uuid4()), str(uuid4()), str(uuid4()), stamp()
        body = {"patient_reference_id": str(uuid4()), "patient_identifiers_confirmed": True, "language": "en",
                "timezone": "Asia/Kolkata", "workflow": "outpatient_general_medicine", "requested_inference_mode": "fully_local", "synthetic_data": True}
        destination = assets / f"{uid}.wav"
        shutil.copyfile(source, destination)
        try:
            with database() as con:
                con.execute("INSERT INTO encounters (id,tenant,clinician,body,created_at) VALUES (?,?,?,?,?)",
                    (eid, str(actor.tenant_id), str(actor.clinician_id), canonical_json(body), created))
                con.execute("INSERT INTO authorizations VALUES (?,?,?,?,NULL)", (str(uuid4()), eid,
                    canonical_json({"scopes": ["recording", "local_processing"], "method": "written", "policy_version": "synthetic-example-v1",
                        "expires_at": datetime.fromtimestamp(datetime.now(timezone.utc).timestamp()+8*3600, timezone.utc).isoformat()}), created))
                con.execute("INSERT INTO uploads (id,encounter,expected_bytes,expected_sha256,status,created_at,expires_at) VALUES (?,?,?,?,?,?,?)",
                    (uid, eid, source.stat().st_size, digest, "complete", created, created))
                metadata["sha256"] = digest
                con.execute("INSERT INTO jobs (id,upload,encounter,status,created_at,updated_at,result) VALUES (?,?,?,'succeeded',?,?,?)",
                    (jid, uid, eid, created, created, canonical_json(metadata)))
                segments = [{**segment, "segment_id": str(uuid4()), "speaker_id": None, "role_status": "public_reference_annotation_requires_review" if public_case else "synthetic_reference_annotation",
                    "alignment_status": "fixture_audio_boundaries", "language": "en", "language_status": "uncertain", "uncertainties": ["clinician_review_required"]} for segment in bundle["segments"]]
                tx = {"schema_version": "1.0", "audio_asset_id": uid, "input_sha256": digest, "duration_ms": metadata["duration_ms"],
                    "segments": segments, "status": "review_required", "source_availability": "available", "review": {},
                    "provenance": {"engine": "public_human_reference_not_asr" if public_case else "synthetic_reference_transcript", "fixture_id": public_case or "outpatient_english_v1", "attribution": bundle.get("attribution", "Synthetic scripted example") },
                    "untranscribed_intervals": [], "review_flags": ["clinician_review_required", "language_support_unverified"]}
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
            rows = con.execute("""SELECT uploads.id,uploads.status,uploads.expected_bytes,jobs.id AS ingest_job_id
                FROM uploads LEFT JOIN jobs ON jobs.upload=uploads.id AND jobs.stage='audio_ingest'
                WHERE uploads.encounter=? ORDER BY uploads.created_at DESC LIMIT 100""", (str(eid),)).fetchall()
            return {"items": [dict(row) for row in rows]}

    @app.get("/v1/encounters")
    def list_encounters(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=10000), actor=Depends(identity)):
        with database() as con:
            rows = con.execute("""SELECT * FROM encounters WHERE tenant=? AND clinician=? AND deleted_at IS NULL
                ORDER BY created_at DESC,id LIMIT ? OFFSET ?""", (str(actor.tenant_id), str(actor.clinician_id), limit, offset)).fetchall()
            return {"items": [{"id": row["id"], "created_at": row["created_at"],
                "patient_reference_id": json.loads(row["body"])["patient_reference_id"],
                "current_transcript_id": row["current_transcript"], "current_note_id": row["current_note"]} for row in rows],
                "next_offset": offset + limit if len(rows) == limit else None}

    @app.get("/v1/encounters/{eid}/workspace")
    def workspace(eid: UUID, actor=Depends(identity)):
        with database() as con:
            row = current(con, eid, actor)
            tx = note = report = approval = None
            if row["current_transcript"]:
                tr, tx = get_tx(con, eid, row["current_transcript"])
                tx = {**tx, "sha256": tr["sha256"]}
            if row["current_note"]:
                nr, note = document(con, eid, row["current_note"])
                note = {**note, "sha256": nr["sha256"]}
                _, report = document(con, eid, note["verification_report_id"], "verification")
                ar = con.execute("SELECT body FROM approvals WHERE note=?", (note["id"],)).fetchone()
                approval = json.loads(ar["body"]) if ar else None
            jobs = con.execute("SELECT id,stage,status,error_code,result,attempts,upload,preview_only FROM jobs WHERE encounter=? ORDER BY created_at DESC LIMIT 20", (str(eid),)).fetchall()
            return {"encounter": {"id": str(eid), **json.loads(row["body"])}, "transcript": tx,
                    "note": note, "verification": report, "approval": approval,
                    "stale": bool(note and (not tx or note["transcript_version_id"] != tx["id"])),
                    "jobs": [{**dict(job), "retryable":job_retryable(job), "progress":job_progress(con,job) if job["status"] in ("queued","running","failed") else None, "result": json.loads(job["result"]) if job["result"] else None} for job in jobs],
                    "exports": [dict(item) for item in con.execute("SELECT id,format,sha256,created_at FROM exports WHERE encounter=?", (str(eid),))]}

    @app.get("/v1/encounters/{eid}/audio/{upload_id}")
    def audio(eid: UUID, upload_id: UUID, channel: int | None = Query(default=None, ge=0, le=7), actor=Depends(identity)):
        with database() as con:
            current(con, eid, actor)
            row = con.execute("SELECT * FROM uploads WHERE id=? AND encounter=? AND status='complete'", (str(upload_id), str(eid))).fetchone()
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
                ingest = con.execute("SELECT result FROM jobs WHERE upload=? AND encounter=? AND stage='audio_ingest' AND status='succeeded'", (str(upload_id), str(eid))).fetchone()
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
            return FileResponse(isolated, media_type="audio/wav", background=BackgroundTask(isolated.unlink, missing_ok=True))
        return FileResponse(path, media_type=row["media_type"])

    @app.post("/v1/encounters/{eid}/manual-transcripts", status_code=201)
    def manual_transcript(eid: UUID, body: ManualTranscript, actor=Depends(identity)):
        with database() as con:
            row = current(con, eid, actor)
            require_processing(con, eid)
            ingest = con.execute("SELECT result FROM jobs WHERE upload=? AND encounter=? AND stage='audio_ingest' AND status='succeeded'",
                                 (str(body.audio_asset_id), str(eid))).fetchone()
            if not ingest:
                raise HTTPException(409, "audio_ingest_required")
            metadata = json.loads(ingest["result"])
            segments, last = [], -1
            for segment in body.segments:
                if segment.end_ms <= segment.start_ms or segment.end_ms > metadata["duration_ms"] or segment.start_ms < last:
                    raise HTTPException(422, "invalid_source_interval")
                segment.text.encode("utf-8")
                last = segment.start_ms
                segments.append({**segment.model_dump(), "segment_id": str(uuid4()), "speaker_id": None,
                    "role_status": "human_confirmed" if segment.role != "unknown" else "unconfirmed",
                    "language": "en", "language_status": "supported" if body.english_confirmed else "uncertain",
                    "alignment_status": "human_estimated", "uncertainties": []})
            gaps, covered = [], 0
            for segment in segments:
                if segment["start_ms"] > covered:
                    gaps.append({"start_ms": covered, "end_ms": segment["start_ms"], "reason": "not_transcribed_unknown_cause"})
                covered = max(covered, segment["end_ms"])
            if covered < metadata["duration_ms"]:
                gaps.append({"start_ms": covered, "end_ms": metadata["duration_ms"], "reason": "not_transcribed_unknown_cause"})
            tx = {"schema_version": "1.0", "audio_asset_id": str(body.audio_asset_id), "input_sha256": metadata["sha256"],
                  "duration_ms": metadata["duration_ms"], "segments": segments, "status": "review_required",
                  "source_availability": "available", "review": body.model_dump(include={"english_confirmed", "source_completeness_reviewed", "source_review_reason"}),
                  "provenance": {"engine": "authorized_manual_transcription"}, "untranscribed_intervals": gaps, "review_flags": []}
            return store_tx(con, eid, str(body.audio_asset_id), tx, actor, row["current_transcript"])

    @app.patch("/v1/encounters/{eid}/transcripts/{tid}", status_code=201)
    def edit_transcript(eid: UUID, tid: UUID, body: TranscriptEdit, if_match: str = Header(alias="If-Match"), actor=Depends(identity)):
        with database() as con:
            row = current(con, eid, actor)
            require_processing(con, eid)
            tr, tx = get_tx(con, eid, tid)
            if_current(row, "current_transcript", tid, tr["sha256"], if_match)
            edits = {str(item.segment_id): item for item in body.segments}
            if len(edits) != len(body.segments) or set(edits) != {item["segment_id"] for item in tx["segments"]}:
                raise HTTPException(422, "segment_set_mismatch")
            for segment in tx["segments"]:
                edit = edits[segment["segment_id"]]
                edit.text.encode("utf-8")
                segment.update(text=edit.text, role=edit.role, parent_segment_id=segment["segment_id"], segment_id=str(uuid4()),
                               role_status="human_confirmed" if edit.role != "unknown" else "unconfirmed",
                               language_status="supported" if body.english_confirmed else "uncertain")
            tx["review"] = body.model_dump(include={"english_confirmed", "source_completeness_reviewed", "source_review_reason", "correction_reason"})
            return store_tx(con, eid, tr["upload"], tx, actor, str(tid))

    @app.post('/v1/encounters/{eid}/transcripts/{tid}/speaker-roles', status_code=201)
    def speaker_roles(eid: UUID, tid: UUID, body: SpeakerRoleConfirmation, if_match: str = Header(alias='If-Match'), actor=Depends(identity)):
        from services.diarization import confirm_roles
        with database() as con:
            row=current(con,eid,actor)
            require_processing(con,eid)
            tr,tx=get_tx(con,eid,tid)
            if_current(row,'current_transcript',tid,tr['sha256'],if_match)
            report=tx.get('diarization')
            if not report:
                raise HTTPException(409,'diarization_required')
            identified=[s for s in report['segments'] if s.get('speaker_id') is not None]
            try:
                confirmed=confirm_roles(identified,body.assignments,clinician_confirmed=body.clinician_confirmed)
            except ValueError:
                raise HTTPException(422,'all_speaker_clusters_require_explicit_roles') from None
            by_interval={(s['start_ms'],s['end_ms'],s['speaker_id']):s for s in confirmed}
            report['segments']=[by_interval.get((s['start_ms'],s['end_ms'],s.get('speaker_id')),s) for s in report['segments']]
            report['role_assignment']='clinician_confirmed'
            report['role_confirmed_by']=str(actor.clinician_id)
            report['role_confirmed_at']=stamp()
            for s in tx['segments']:
                if s.get('speaker_id') in body.assignments:
                    s['role']=body.assignments[s['speaker_id']]
                    s['role_status']='human_confirmed'
                    s['uncertainties']=[u for u in s['uncertainties'] if u!='speaker_unassigned']
            return store_tx(con,eid,tr['upload'],tx,actor,str(tid))

    @app.get("/v1/encounters/{eid}/facts")
    def facts(eid: UUID, actor=Depends(identity)):
        with database() as con:
            row = current(con, eid, actor)
            if not row["current_transcript"]:
                raise HTTPException(409, "transcript_required")
            tr, tx = get_tx(con, eid, row["current_transcript"])
            return {"transcript_version_id": tr["id"], "transcript_sha256": tr["sha256"], "facts": propose_facts(tx)}

    @app.post("/v1/encounters/{eid}/drafts", status_code=201)
    def draft(eid: UUID, body: DraftInput, actor=Depends(identity)):
        with database() as con:
            row = current(con, eid, actor)
            require_processing(con, eid)
            if row["current_transcript"] != str(body.transcript_version_id):
                raise HTTPException(412, "stale_transcript")
            if row["current_note"] and con.execute("SELECT 1 FROM approvals WHERE note=?", (row["current_note"],)).fetchone():
                raise HTTPException(409, "amendment_required")
            tr, tx = get_tx(con, eid, body.transcript_version_id)
            return save_note(con, eid, tr, tx, body.facts, actor, row["current_note"])

    @app.get("/v1/encounters/{eid}/notes/{nid}")
    def note(eid: UUID, nid: UUID, actor=Depends(identity)):
        with database() as con:
            current(con, eid, actor)
            row, body = document(con, eid, nid)
            return JSONResponse(content={**body, "sha256": row["sha256"]}, headers={"ETag": f'"{row["sha256"]}"'})

    @app.patch("/v1/encounters/{eid}/notes/{nid}", status_code=201)
    def edit_note(eid: UUID, nid: UUID, body: NoteEdit, if_match: str = Header(alias="If-Match"), actor=Depends(identity)):
        with database() as con:
            row = current(con, eid, actor)
            require_processing(con, eid)
            nr, old = document(con, eid, nid)
            if_current(row, "current_note", nid, nr["sha256"], if_match)
            if con.execute("SELECT 1 FROM approvals WHERE note=?", (str(nid),)).fetchone():
                raise HTTPException(409, "amendment_required")
            if row["current_transcript"] != str(body.transcript_version_id):
                raise HTTPException(412, "stale_transcript")
            tr, tx = get_tx(con, eid, body.transcript_version_id)
            return save_note(con, eid, tr, tx, body.facts, actor, str(nid), body.amendment_reason or old["amendment_reason"])

    @app.get("/v1/encounters/{eid}/verification")
    def verification(eid: UUID, actor=Depends(identity)):
        with database() as con:
            row = current(con, eid, actor)
            if not row["current_note"]:
                raise HTTPException(409, "note_required")
            _, body = document(con, eid, row["current_note"])
            _, report = document(con, eid, body["verification_report_id"], "verification")
            return {**report, "stale": body["transcript_version_id"] != row["current_transcript"]}

    @app.post("/v1/encounters/{eid}/findings/{fid}/resolve", status_code=201)
    def resolve(eid: UUID, fid: UUID, body: ResolutionInput, actor=Depends(identity)):
        from services.review.models import Fact
        with database() as con:
            row = current(con, eid, actor)
            require_processing(con, eid)
            nr, old = document(con, eid, row["current_note"])
            if nr["sha256"] != body.expected_note_sha256:
                raise HTTPException(412, "stale_note")
            if con.execute("SELECT 1 FROM approvals WHERE note=?", (nr["id"],)).fetchone():
                raise HTTPException(409, "amendment_required")
            _, report = document(con, eid, old["verification_report_id"], "verification")
            if not any(item["finding_id"] == str(fid) and item["fact_id"] == str(body.fact_id) for item in report["findings"]):
                raise HTTPException(404, "finding_not_found")
            if old["transcript_version_id"] != row["current_transcript"]:
                raise HTTPException(412, "stale_transcript")
            values = []
            for value in old["facts"]:
                value = {key: value[key] for key in Fact.model_fields if key in value}
                if value["fact_id"] == str(body.fact_id):
                    if value["text"] == body.corrected_text:
                        raise HTTPException(422, "clinical_correction_required")
                    value.update(text=body.corrected_text, clarification=body.reason, reviewed=True, critical_reviewed=True)
                values.append(Fact.model_validate(value))
            tr, tx = get_tx(con, eid, old["transcript_version_id"])
            result = save_note(con, eid, tr, tx, values, actor, nr["id"], old["amendment_reason"])
            audit(con, actor, "finding_corrected_new_version", str(fid))
            return result

    @app.post("/v1/encounters/{eid}/approvals", status_code=201)
    def approve(eid: UUID, body: ApprovalInput, actor=Depends(identity)):
        with database() as con:
            row = current(con, eid, actor)
            require_processing(con, eid)
            nr, note = document(con, eid, body.note_version_id)
            if row["current_note"] != nr["id"] or body.expected_note_sha256 != nr["sha256"]:
                raise HTTPException(412, "stale_note")
            if row["current_transcript"] != note["transcript_version_id"] or str(body.verification_report_id) != note["verification_report_id"]:
                raise HTTPException(412, "stale_inputs_or_verification")
            tr, tx = get_tx(con, eid, row["current_transcript"])
            _, report = document(con, eid, body.verification_report_id, "verification")
            if report["note_sha256"] != nr["sha256"] or report["transcript_sha256"] != tr["sha256"]:
                raise HTTPException(412, "stale_verification")
            if report["findings"] or findings_for(note, tx):
                raise HTTPException(409, "blocking_findings")
            existing = con.execute("SELECT body FROM approvals WHERE note=?", (nr["id"],)).fetchone()
            if existing:
                return json.loads(existing["body"])
            aid, created = str(uuid4()), stamp()
            approved = {"id": aid, "note_version_id": nr["id"], "note_sha256": nr["sha256"],
                "transcript_version_id": tr["id"], "transcript_sha256": tr["sha256"],
                "verification_report_id": report["id"], "clinician_id": str(actor.clinician_id),
                "approved_at": created, "attestation_version": body.attestation_version,
                "patient_identifiers_reconfirmed": True}
            con.execute("INSERT INTO approvals VALUES (?,?,?,?,?)", (aid, str(eid), nr["id"], canonical_json(approved), created))
            audit(con, actor, "exact_version_approved", aid)
            return approved

    @app.post("/v1/encounters/{eid}/amendments", status_code=201)
    def amend(eid: UUID, body: AmendmentInput, actor=Depends(identity)):
        from services.review.models import Fact
        with database() as con:
            row = current(con, eid, actor)
            require_processing(con, eid)
            ar = con.execute("SELECT * FROM approvals WHERE id=? AND encounter=?", (str(body.approval_id), str(eid))).fetchone()
            if not ar:
                raise HTTPException(404, "approval_not_found")
            if row["current_note"] != ar["note"]:
                raise HTTPException(412, "amend_current_approved_version_only")
            _, old = document(con, eid, ar["note"])
            tr, tx = get_tx(con, eid, row["current_transcript"])
            if tr["id"] != old["transcript_version_id"]:
                # Fresh evidence must be selected against the corrected transcript.
                values = [Fact.model_validate(item) for item in propose_facts(tx)]
            else:
                values = [Fact.model_validate({key: value[key] for key in Fact.model_fields if key in value}) for value in old["facts"]]
            return save_note(con, eid, tr, tx, values, actor, old["id"], body.reason)

    @app.post("/v1/encounters/{eid}/exports", status_code=201)
    def export(eid: UUID, body: ExportInput, actor=Depends(identity)):
        with database() as con:
            current(con, eid, actor)
            ar = con.execute("SELECT * FROM approvals WHERE id=? AND encounter=?", (str(body.approval_id), str(eid))).fetchone()
            if not ar:
                raise HTTPException(404, "approval_not_found")
            existing = con.execute("SELECT * FROM exports WHERE approval=? AND format=?", (ar["id"], body.format)).fetchone()
            if existing:
                return {"id": existing["id"], "sha256": existing["sha256"], "download_url": f"/v1/encounters/{eid}/exports/{existing['id']}"}
            nr, note = document(con, eid, ar["note"])
            approval = json.loads(ar["body"])
            if nr["sha256"] != approval["note_sha256"]:
                raise HTTPException(409, "approved_artifact_integrity_failure")
            artifact = render_export(note, approval, body.format)
            digest = hashlib.sha256(artifact.encode("utf-8")).hexdigest()
            xid = str(uuid4())
            con.execute("INSERT INTO exports VALUES (?,?,?,?,?,?,?)", (xid, str(eid), ar["id"], body.format, artifact, digest, stamp()))
            audit(con, actor, "approved_export_created", xid)
            return {"id": xid, "sha256": digest, "download_url": f"/v1/encounters/{eid}/exports/{xid}"}

    @app.get("/v1/encounters/{eid}/exports/{xid}")
    def download(eid: UUID, xid: UUID, actor=Depends(identity)):
        with database() as con:
            current(con, eid, actor)
            row = con.execute("SELECT * FROM exports WHERE id=? AND encounter=?", (str(xid), str(eid))).fetchone()
            if not row:
                raise HTTPException(404, "export_not_found")
            audit(con, actor, "approved_export_downloaded", str(xid))
            extension = {"markdown": "md", "text": "txt", "json": "json", "fhir": "json"}[row["format"]]
            return Response(row["artifact"], media_type="application/json" if extension == "json" else "text/plain; charset=utf-8",
                            headers={"Content-Disposition": f'attachment; filename="approved-note-{xid}.{extension}"', "ETag": f'"{row["sha256"]}"'})

    @app.get("/v1/encounters/{eid}/audit")
    def audit_trail(eid: UUID, actor=Depends(identity)):
        with database() as con:
            current(con, eid, actor)
            ids = {str(eid)}
            for table in ("review_metrics", "model_proposals", "uploads", "jobs", "documents", "transcript_versions", "approvals", "exports", "authorizations"):
                ids.update(item[0] for item in con.execute(f"SELECT id FROM {table} WHERE encounter=?", (str(eid),)))
            rows = con.execute("SELECT * FROM audit WHERE tenant=? ORDER BY time DESC LIMIT 2000", (str(actor.tenant_id),)).fetchall()
            return {"items": [dict(item) for item in rows if item["resource"] in ids][:200]}

    @app.post("/v1/encounters/{eid}/deletion-requests", status_code=202)
    def delete_request(eid: UUID, actor=Depends(identity)):
        with database() as con:
            row = current(con, eid, actor)
            if row["legal_hold"] or con.execute("SELECT 1 FROM approvals WHERE encounter=?", (str(eid),)).fetchone():
                raise HTTPException(409, "record_retention_review_required")
            rid, created = str(uuid4()), stamp()
            con.execute("INSERT INTO deletion_requests VALUES (?,?,?, ?,NULL)", (rid, str(eid), "pending", created))
            con.execute("UPDATE encounters SET deleted_at=? WHERE id=?", (created, str(eid)))
            con.execute("UPDATE jobs SET status='cancelled',lease_token=NULL,lease_expires_at=NULL WHERE encounter=? AND status IN ('queued','running')", (str(eid),))
            audit(con, actor, "encounter_tombstoned", str(eid))
            return {"id": rid, "status": "pending", "backup_expiry": "requires_operator_confirmation"}

    @app.get("/v1/deletion-requests/{rid}")
    def deletion_status(rid: UUID, actor=Depends(identity)):
        with database() as con:
            row = con.execute("""SELECT deletion_requests.* FROM deletion_requests JOIN encounters
                ON encounters.id=deletion_requests.encounter WHERE deletion_requests.id=?
                AND encounters.tenant=? AND encounters.clinician=?""", (str(rid), str(actor.tenant_id), str(actor.clinician_id))).fetchone()
            if not row:
                raise HTTPException(404, "deletion_request_not_found")
            return {**dict(row), "backup_expiry": "requires_operator_confirmation"}
