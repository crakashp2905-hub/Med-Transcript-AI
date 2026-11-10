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
from services.domain_contracts import validate_record
from services.proposal_integrity import decode_proposal


class ExtractRequest(Strict):
    transcript_version_id:UUID
    mode:Literal['rules','local_model']='rules'
    segment_ids:list[UUID]|None=Field(default=None,min_length=1,max_length=20)


class VerifyRequest(Strict):
    note_version_id:UUID
    fact_ids:list[UUID]|None=Field(default=None,min_length=1,max_length=300)


class RetranscribeRequest(Strict):
    audio_asset_id:str=Field(min_length=1,max_length=200)
    transcript_version_id:UUID
    start_ms:int=Field(ge=0)
    end_ms:int=Field(gt=0)
    candidate_text:str=Field(min_length=1,max_length=4000)


def run_semantic_batches(provider,claims):
    """All-or-nothing advisory verification over bounded, exact-ID batches."""
    identifiers=[str(claim['fact_id']) for claim in claims]
    if not 1<=len(claims)<=300 or len(set(identifiers))!=len(identifiers):
        raise ValueError('invalid_semantic_scope')
    verdicts=[];provenance=[]
    for start in range(0,len(claims),20):
        batch=claims[start:start+20]
        result=provider.check_claims(batch,authorized=True,synthetic=True)
        if not isinstance(result,dict):raise ValueError('malformed_semantic_batch')
        rows=result.get('verdicts')
        expected={str(item['fact_id']) for item in batch}
        if (not isinstance(rows,list) or len(rows)!=len(batch)
            or {str(item.get('fact_id')) for item in rows if isinstance(item,dict)}!=expected):
            raise ValueError('semantic_batch_coverage_mismatch')
        for item in rows:
            source=next(claim['evidence'] for claim in batch if str(claim['fact_id'])==str(item['fact_id']))
            quote=item.get('evidence_quote')
            if not isinstance(quote,str) or quote not in source or item.get('label')=='supported' and not quote:
                raise ValueError('semantic_batch_quote_mismatch')
        verdicts.extend(rows)
        provenance.append(result.get('provenance',{}))
    if len(verdicts)!=len(claims) or {str(row['fact_id']) for row in verdicts}!=set(identifiers):
        raise ValueError('semantic_total_coverage_mismatch')
    return {'verdicts':verdicts,'status':'advisory_only_not_approval',
            'provenance':{'mode':'bounded_batches_v1','batch_size':20,'batches':provenance},
            'batch_count':len(provenance),'cannot_clear_existing_findings':True}


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
        try:validate_record(kind,result)
        except ValueError:raise HTTPException(422,'clinical_proposal_schema_rejected') from None
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
        from services.application_pipeline import enrich_fact_proposal
        result['application_enrichment']=enrich_fact_proposal(
            transcript_id=tx['id'], facts=result.get('facts', []),
            relationships=result.get('source_relationships', {}))
        result['facts']=result['application_enrichment']['facts']
        result['source_batch']={'segment_ids':[s['segment_id'] for s in analysis_tx['segments']],
            'total_source_segments':len(tx['segments']),'unselected_segment_ids':[s['segment_id'] for s in tx['segments'] if s['segment_id'] not in selected],
            'scope':'processed_source_batch_not_clinician_completeness_review'}
        with database() as con:return save(con,eid,actor,'fact_proposal',result,tx,tr['sha256'])

    @app.post('/v1/encounters/{eid}/retranscriptions',status_code=201)
    def retranscribe(eid:UUID,body:RetranscribeRequest,actor=Depends(identity)):
        from services.asr.retranscribe_span import retranscribe_span
        with database() as con:
            row=encounter(con,eid,actor); require_processing(con,eid)
            if row['current_transcript'] != str(body.transcript_version_id):
                raise HTTPException(412,'stale_transcript')
            candidate=retranscribe_span(audio_asset_id=body.audio_asset_id,
                start_ms=body.start_ms,end_ms=body.end_ms,
                source_transcript_version=str(body.transcript_version_id),
                candidate_text=body.candidate_text)
            audit(con,actor,'retranscription_candidate_created',body.audio_asset_id)
            return candidate

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
            if body.fact_ids and len(selected)!=len(body.fact_ids) or not selected<=lookup.keys() or not 1<=len(selected)<=300:
                raise HTTPException(422,'invalid_semantic_fact_selection')
            claims=[{'fact_id':f['fact_id'],'text':f['text'],'evidence':f['evidence']['quote']} for f in note['facts'] if f['fact_id'] in selected]
        try:
            with local_inference_slot() as ready:
                if not ready:raise HTTPException(503,'local_inference_busy')
                result=run_semantic_batches(app.state.clinical_models,claims)
        except ValueError:raise HTTPException(422,'semantic_check_failed_no_output_admitted') from None
        result.update(checked_fact_ids=sorted(selected),evidence_linked_fact_count=len(lookup),
            unchecked_fact_ids=sorted(lookup.keys()-selected),independent_clinical_calibration=False,
            total_note_fact_count=len(note['facts']),
            unverifiable_no_source_fact_ids=sorted(f['fact_id'] for f in note['facts'] if not f.get('excluded') and not f.get('evidence')),
            excluded_fact_ids=sorted(f['fact_id'] for f in note['facts'] if f.get('excluded')),
            completion_status='complete_evidence_linked_scope' if selected==lookup.keys() else 'partial_selected_scope')
        with database() as con:return save(con,eid,actor,'semantic_check',result,tx,tr['sha256'],note['id'])

    @app.get('/v1/encounters/{eid}/clinical-proposals/{pid}')
    def proposal(eid:UUID,pid:UUID,actor=Depends(identity)):
        with database() as con:
            row=encounter(con,eid,actor)
            saved=con.execute("SELECT * FROM model_proposals WHERE encounter=? AND id=? AND kind IN ('fact_proposal','semantic_check')",(str(eid),str(pid))).fetchone()
            if saved is None:raise HTTPException(404,'clinical_proposal_not_found')
            result=decode_proposal(con,saved,eid)
            result['stale']=row['current_transcript']!=result['transcript_version_id'] or bool(result.get('note_version_id') and row['current_note']!=result['note_version_id'])
            return result
