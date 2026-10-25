import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException
from pydantic import Field
from services.review.models import Strict
from services.asr.profiles import canonical_json, content_sha256
from services.usability_metrics import note_correction


class StartReview(Strict):
    note_version_id: UUID
    client_request_id: UUID | None = None


class FinishReview(Strict):
    note_version_id: UUID
    self_reported_active_ms: int | None = Field(default=None, ge=0, le=86400000, strict=True)


def register(app, database, identity, encounter, require_processing, document, audit):
    @app.get('/v1/encounters/{eid}/review-sessions')
    def sessions(eid: UUID,actor=Depends(identity)):
        with database() as con:
            encounter(con,eid,actor)
            rows=con.execute("SELECT p.body,m.body AS completion FROM model_proposals p LEFT JOIN review_metrics m ON m.session=p.id WHERE p.encounter=? AND p.kind='review_session' ORDER BY p.created_at DESC LIMIT 100",(str(eid),)).fetchall()
            return {'items':[{**json.loads(r['body']),'completion':json.loads(r['completion']) if r['completion'] else None} for r in rows],
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
            existing=con.execute('SELECT encounter,body FROM model_proposals WHERE id=?',(sid,)).fetchone()
            if existing:
                old=json.loads(existing['body'])
                if existing['encounter']!=str(eid) or old.get('actor')!=str(actor.clinician_id) or old.get('note_version_id')!=str(body.note_version_id):
                    raise HTTPException(409,'review_session_request_conflict')
                return old
            value={'id':sid,'note_version_id':str(body.note_version_id),'actor':str(actor.clinician_id),'started_at':stamp}
            con.execute('INSERT INTO model_proposals VALUES (?,?,?,?,?,?,?)',(sid,str(eid),'review_session',1,content_sha256(value),canonical_json(value),stamp))
            audit(con,actor,'review_session_started',sid)
            return value

    @app.post('/v1/encounters/{eid}/review-sessions/{sid}/complete')
    def finish(eid: UUID,sid: UUID,body: FinishReview,actor=Depends(identity)):
        with database() as con:
            row=encounter(con,eid,actor)
            require_processing(con,eid)
            source=con.execute("SELECT body FROM model_proposals WHERE encounter=? AND id=? AND kind='review_session'",(str(eid),str(sid))).fetchone()
            if source is None:
                raise HTTPException(404,'review_session_not_found')
            session=json.loads(source['body'])
            if session['actor']!=str(actor.clinician_id):
                raise HTTPException(404,'review_session_not_found')
            existing=con.execute('SELECT body FROM review_metrics WHERE session=?',(str(sid),)).fetchone()
            if existing:
                result=json.loads(existing['body'])
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
                source_changed=before['transcript_version_id']!=after['transcript_version_id'])
            con.execute('INSERT INTO review_metrics VALUES (?,?,?,?,?)',(mid,str(sid),str(eid),canonical_json(measured),stamp.isoformat()))
            audit(con,actor,'review_metrics_created',mid)
            return measured
