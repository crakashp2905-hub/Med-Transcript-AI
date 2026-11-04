"""Transcripts routes with preserved exact-version review contracts."""
import json
from uuid import UUID, uuid4

from fastapi import Depends, Header, HTTPException

from services.review.engine import propose_facts
from services.review.models import ManualTranscript, TranscriptEdit, SpeakerRoleConfirmation


from services.review.service import ReviewService

def register(app, services: ReviewService):
    database = services.database
    identity = services.identity
    require_processing = services.require_processing
    stamp = services.stamp
    get_tx = services.get_tx
    current = services.current
    if_current = services.if_current
    store_tx = services.store_tx

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
