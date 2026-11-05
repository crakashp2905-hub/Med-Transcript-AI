import json
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import Field
from services.review.models import Strict
from services.asr.profiles import canonical_json, content_sha256
from services.usability_metrics import note_correction
from services.domain_contracts import validate_record
from services.proposal_integrity import decode_proposal
from services.metric_integrity import decode_metric,seal as seal_metric


class StartReview(Strict):
    note_version_id: UUID
    client_request_id: UUID | None = None
    drafting_arm: Literal['unspecified','manual','deterministic','local_qwen'] = 'unspecified'


class FinishReview(Strict):
    note_version_id: UUID
    self_reported_active_ms: int | None = Field(default=None, ge=0, le=86400000, strict=True)


def register(app, database, identity, encounter, require_processing, document, audit):
    @app.get('/v1/encounters/{eid}/review-sessions')
    def sessions(eid: UUID,actor=Depends(identity)):
        with database() as con:
            encounter(con,eid,actor)
            rows=con.execute("SELECT * FROM model_proposals WHERE encounter=? AND kind='review_session' ORDER BY created_at DESC LIMIT 100",(str(eid),)).fetchall()
            values=[]
            for row in rows:
                value=decode_proposal(con,row,eid)
                metric=con.execute('SELECT * FROM review_metrics WHERE session=?',(row['id'],)).fetchone()
                values.append({**value,'completion':decode_metric(con,metric,eid,row['id'])})
            return {'items':values,
                'limit':100,'active_time_verified':False}

    @app.post('/v1/encounters/{eid}/review-sessions',status_code=201)
    def start(eid: UUID, body: StartReview, actor=Depends(identity)):
        with database() as con:
            row=encounter(con,eid,actor)
            require_processing(con,eid)
            if row['current_note']!=str(body.note_version_id):
                raise HTTPException(412,'stale_note')
            _,note=document(con,eid,body.note_version_id)
            sid,stamp=str(body.client_request_id or uuid4()),datetime.now(timezone.utc).isoformat()
            existing=con.execute('SELECT * FROM model_proposals WHERE id=?',(sid,)).fetchone()
            if existing:
                old=decode_proposal(con,existing,eid)
                if existing['encounter']!=str(eid) or old.get('actor')!=str(actor.clinician_id) or old.get('note_version_id')!=str(body.note_version_id) or old.get('drafting_arm','unspecified')!=body.drafting_arm:
                    raise HTTPException(409,'review_session_request_conflict')
                return old
            value={'id':sid,'note_version_id':str(body.note_version_id),'actor':str(actor.clinician_id),'started_at':stamp,
                'drafting_arm':body.drafting_arm,'arm_attribution':'clinician_selected_not_independently_verified'}
            validate_record('review_session',value)
            con.execute('INSERT INTO model_proposals VALUES (?,?,?,?,?,?,?)',(sid,str(eid),'review_session',1,content_sha256(value),canonical_json(value),stamp))
            audit(con,actor,'review_session_started',sid)
            return value

    @app.post('/v1/encounters/{eid}/review-sessions/{sid}/complete')
    def finish(eid: UUID,sid: UUID,body: FinishReview,actor=Depends(identity)):
        with database() as con:
            row=encounter(con,eid,actor)
            require_processing(con,eid)
            source=con.execute("SELECT * FROM model_proposals WHERE encounter=? AND id=? AND kind='review_session'",(str(eid),str(sid))).fetchone()
            if source is None:
                raise HTTPException(404,'review_session_not_found')
            session=decode_proposal(con,source,eid)
            if session['actor']!=str(actor.clinician_id):
                raise HTTPException(404,'review_session_not_found')
            existing=con.execute('SELECT * FROM review_metrics WHERE session=?',(str(sid),)).fetchone()
            result=decode_metric(con,existing,eid,sid)
            if existing:
                if result['after_note']!=str(body.note_version_id) or result['self_reported_active_ms']!=body.self_reported_active_ms:
                    raise HTTPException(409,'review_completion_request_conflict')
                return result
            if row['current_note']!=str(body.note_version_id):
                raise HTTPException(412,'stale_note')
            _,before=document(con,eid,session['note_version_id'])
            _,after=document(con,eid,body.note_version_id)
            stamp=datetime.now(timezone.utc)
            wall=max(0,round((stamp-datetime.fromisoformat(session['started_at'])).total_seconds()*1000))
            try:
                measured=note_correction(before,after,wall,body.self_reported_active_ms)
            except ValueError:
                raise HTTPException(422,'active_time_exceeds_observed_session') from None
            mid=str(uuid4())
            measured.update(id=mid,session_id=str(sid),before_note=session['note_version_id'],after_note=str(body.note_version_id),
                source_changed=before['transcript_version_id']!=after['transcript_version_id'],drafting_arm=session.get('drafting_arm','unspecified'),arm_attribution='clinician_selected_not_independently_verified')
            con.execute('INSERT INTO review_metrics VALUES (?,?,?,?,?)',(mid,str(sid),str(eid),canonical_json(measured),stamp.isoformat()))
            seal_metric(con,measured)
            audit(con,actor,'review_metrics_created',mid)
            return measured
