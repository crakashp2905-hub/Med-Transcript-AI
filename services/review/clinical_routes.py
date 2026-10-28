"""Scoped immutable local extraction/verifier proposals with late-publication fences."""
import json
from contextlib import nullcontext
from services.inference_slot import local_inference_slot
import os
from datetime import datetime,timezone
from typing import Literal
from uuid import UUID,uuid4
from fastapi import Depends,HTTPException
from pydantic import Field
from services.review.models import Strict
from services.review.clinical_models import LocalClinicalModels,RuleExtractor
from services.asr.profiles import canonical_json,content_sha256


class ExtractRequest(Strict):
    transcript_version_id:UUID
    mode:Literal['rules','local_model']='rules'
    segment_ids:list[UUID]|None=Field(default=None,min_length=1,max_length=20)


class VerifyRequest(Strict):
    note_version_id:UUID
    fact_ids:list[UUID]|None=Field(default=None,min_length=1,max_length=20)


def register(app,database,identity,encounter,require_processing,get_tx,document,audit):
    app.state.clinical_models=LocalClinicalModels(os.environ.get('MED_TRANSCRIPT_LOCAL_CLINICAL_MODELS')=='1')

    def save(con,eid,actor,kind,result,tx,transcript_hash,note_id=None):
        row=encounter(con,eid,actor)
        require_processing(con,eid)
        current,_=get_tx(con,eid,tx['id'])
        if row['current_transcript']!=tx['id'] or current['sha256']!=transcript_hash or note_id and row['current_note']!=note_id:
            raise HTTPException(412,'source_changed_during_clinical_inference')
        pid=str(uuid4());stamp=datetime.now(timezone.utc).isoformat()
        result.update(id=pid,transcript_version_id=tx['id'],transcript_sha256=transcript_hash,
            note_version_id=note_id,status='unreviewed_proposal_not_approvable')
        con.execute('INSERT INTO model_proposals VALUES (?,?,?,?,?,?,?)',
            (pid,str(eid),kind,1,content_sha256(result),canonical_json(result),stamp))
        audit(con,actor,kind+'_created',pid)
        return result

    @app.post('/v1/encounters/{eid}/fact-proposals',status_code=201)
    def extract(eid:UUID,body:ExtractRequest,actor=Depends(identity)):
        with database() as con:
            row=encounter(con,eid,actor);require_processing(con,eid)
            if row['current_transcript']!=str(body.transcript_version_id):raise HTTPException(412,'stale_transcript')
            tr,tx=get_tx(con,eid,body.transcript_version_id)
            selected={str(sid) for sid in body.segment_ids} if body.segment_ids else {s['segment_id'] for s in tx['segments']}
            if body.segment_ids and len(selected)!=len(body.segment_ids) or not selected<={s['segment_id'] for s in tx['segments']}:
                raise HTTPException(422,'invalid_extraction_source_batch')
            analysis_tx={**tx,'segments':[s for s in tx['segments'] if s['segment_id'] in selected]}
        provider=RuleExtractor() if body.mode=='rules' else app.state.clinical_models
        try:
            with (local_inference_slot() if body.mode=='local_model' else nullcontext(True)) as ready:
                if not ready:raise HTTPException(503,'local_inference_busy')
                result=provider.extract_facts(analysis_tx,authorized=True,synthetic=True)
        except ValueError:raise HTTPException(422,'clinical_extraction_failed_no_output_admitted') from None
        from services.review.relationships import analyze_transcript
        try:result['source_relationships']=analyze_transcript(analysis_tx)
        except ValueError:raise HTTPException(422,'clinical_relationship_output_rejected') from None
        result['source_batch']={'segment_ids':[s['segment_id'] for s in analysis_tx['segments']],
            'total_source_segments':len(tx['segments']),'unselected_segment_ids':[s['segment_id'] for s in tx['segments'] if s['segment_id'] not in selected],
            'scope':'processed_source_batch_not_clinician_completeness_review'}
        with database() as con:return save(con,eid,actor,'fact_proposal',result,tx,tr['sha256'])

    @app.post('/v1/encounters/{eid}/semantic-checks',status_code=201)
    def verify(eid:UUID,body:VerifyRequest,actor=Depends(identity)):
        with database() as con:
            row=encounter(con,eid,actor);require_processing(con,eid)
            if row['current_note']!=str(body.note_version_id):raise HTTPException(412,'stale_note')
            _,note=document(con,eid,body.note_version_id)
            if row['current_transcript']!=note['transcript_version_id']:raise HTTPException(412,'stale_transcript')
            tr,tx=get_tx(con,eid,note['transcript_version_id'])
            selected={str(fid) for fid in body.fact_ids} if body.fact_ids else {f['fact_id'] for f in note['facts'] if not f.get('excluded') and f.get('evidence')}
            lookup={f['fact_id']:f for f in note['facts'] if not f.get('excluded') and f.get('evidence')}
            if not selected<=lookup.keys() or not 1<=len(selected)<=20:raise HTTPException(422,'select_up_to_twenty_evidence_linked_facts')
            claims=[{'fact_id':f['fact_id'],'text':f['text'],'evidence':f['evidence']['quote']} for f in note['facts'] if f['fact_id'] in selected]
        try:
            with local_inference_slot() as ready:
                if not ready:raise HTTPException(503,'local_inference_busy')
                result=app.state.clinical_models.check_claims(claims,authorized=True,synthetic=True)
        except ValueError:raise HTTPException(422,'semantic_check_failed_no_output_admitted') from None
        result.update(checked_fact_ids=sorted(selected),evidence_linked_fact_count=len(lookup),
            unchecked_fact_ids=sorted(lookup.keys()-selected),independent_clinical_calibration=False)
        with database() as con:return save(con,eid,actor,'semantic_check',result,tx,tr['sha256'],note['id'])

    @app.get('/v1/encounters/{eid}/clinical-proposals/{pid}')
    def proposal(eid:UUID,pid:UUID,actor=Depends(identity)):
        with database() as con:
            row=encounter(con,eid,actor)
            saved=con.execute("SELECT body FROM model_proposals WHERE encounter=? AND id=? AND kind IN ('fact_proposal','semantic_check')",(str(eid),str(pid))).fetchone()
            if saved is None:raise HTTPException(404,'clinical_proposal_not_found')
            result=json.loads(saved['body'])
            result['stale']=row['current_transcript']!=result['transcript_version_id'] or bool(result.get('note_version_id') and row['current_note']!=result['note_version_id'])
            return result
