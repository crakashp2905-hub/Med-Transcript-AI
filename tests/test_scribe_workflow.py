import io
import wave
from copy import deepcopy
from uuid import uuid4
import pytest
from services.api.ingest import run_once as ingest_once
from services.asr.worker import run_once as asr_once
from services.conversation_experiment import windows, join_text
from services.review.clinical_models import LocalClinicalModels, Extraction
from services.review.providers import validate
from tests.test_transcription import environment
from tests.test_foundation import setup, queue_upload, headers
from tests.test_review_workflow import prepare, draft, approve


@pytest.mark.parametrize('seconds',[1200,1800])
def test_full_duration_upload_worker_and_retry(environment,seconds):
    """Long PCM transport/lease test using a stub recognizer, not ASR quality evidence."""
    env=environment
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as out:
        out.setparams((1,2,16000,0,'NONE','not compressed'))
        for _ in range(seconds):out.writeframesraw(b'\x01\x00'*16000)
    eid,upload,_,_=queue_upload(env.client,buffer.getvalue())
    assert ingest_once(env.path,env.assets)['status']=='succeeded'
    route=f'/v1/encounters/{eid}/transcriptions'
    body={'audio_asset_id':upload['id'],'inference_profile_id':env.profile.profile_id}
    first=env.client.post(route,json=body,headers=headers())
    assert first.status_code==202
    assert env.client.post(route,json=body,headers=headers()).json()['job_id']==first.json()['job_id']
    class LongAdapter:
        def __init__(self,profile):pass
        def transcribe(self,source,metadata,checkpoint):
            checkpoint()
            assert metadata['frames']==seconds*16000
            return {'duration_seconds':seconds,'segments':[
                {'start_seconds':start,'end_seconds':min(seconds,start+30),'text':'Synthetic long-workflow test speech.'}
                for start in range(0,seconds,30)]}
    assert asr_once(env.path,env.assets,LongAdapter)['status']=='succeeded'
    ws=env.client.get(f'/v1/encounters/{eid}/workspace',headers=headers()).json()
    tx=ws['transcript']
    assert tx['duration_ms']==seconds*1000 and not tx['untranscribed_intervals']
    assert tx['segments'][-1]['end_ms']==seconds*1000
    assert ws['approval'] is None and ws['note'] is None
    assert asr_once(env.path,env.assets,LongAdapter) is None


@pytest.mark.parametrize('mode',['fixed','overlap','speech_aware'])
def test_chunk_windows_cover_all_samples_without_invalid_bounds(mode):
    pcm=b'\0\0'*16000*73
    end=0
    for a,b in windows(pcm,mode):
        assert 0<=a<b<=len(pcm)//2 and a<=end
        end=max(end,b)
    assert end==len(pcm)//2


def test_overlap_stitch_retains_unmatched_text():
    assert join_text('Patient has cough','has cough and fever',True)==('Patient has cough and fever',2)
    assert join_text('No fever','No pain',True)==('No fever No pain',0)


def test_model_omission_retains_explicit_unreviewed_baseline(monkeypatch):
    sid=str(uuid4());text='Patient reports cough. Patient denies fever.'
    model=LocalClinicalModels(enabled=True)
    monkeypatch.setattr(model,'complete',lambda *args: (Extraction(facts=[]),{'engine':'stub_not_real_model'}))
    result=model.extract_facts({'segments':[{'segment_id':sid,'text':text}]},authorized=True,synthetic=True)
    assert result['source_span_fallback_count']==2 and len(result['facts'])==2
    assert result['findings'][0]['code']=='model_extraction_coverage_requires_review'
    assert all(not f['reviewed'] and not f['critical_reviewed'] for f in result['facts'])
    for fact in result['facts']:
        e=fact['evidence'];assert text[e['start_char']:e['end_char']]==e['quote']==fact['text']


def test_merged_draft_is_explicitly_flagged():
    facts=[{'fact_id':'one','section':'subjective','text':'Cough.','reviewed':True},
           {'fact_id':'two','section':'subjective','text':'Fever.','reviewed':True}]
    result=validate({'statements':[{'section':'subjective','text':'Cough. Fever.','fact_ids':['one','two']}]},facts)
    assert any(f['code']=='merged_facts_requires_atomic_review' for f in result['findings'])


def test_proposal_baseline_source_edit_and_stale_approval(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path,'Patient reports cough.')
    original=draft(client,eid,tx,facts)['note']
    proposal=client.post(f'/v1/encounters/{eid}/draft-proposals',headers=headers(),json={
        'transcript_version_id':tx['id'],'facts':facts})
    assert proposal.status_code==201
    assert proposal.json()['deterministic_baseline']['draft']['statements'][0]['text']==facts[0]['text']
    assert client.get(f'/v1/encounters/{eid}/workspace',headers=headers()).json()['note']['id']==original['id']
    patch={'segments':[{'segment_id':s['segment_id'],'text':'Patient reports fever.','role':'patient'} for s in tx['segments']],
           'english_confirmed':True,'source_completeness_reviewed':True,
           'source_review_reason':'Synthetic corrected source independently checked.',
           'correction_reason':'Correct the synthetic symptom against the scripted recording.'}
    result=client.patch(f"/v1/encounters/{eid}/transcripts/{tx['id']}",headers={**headers(),'If-Match':f'"{tx["sha256"]}"'},json=patch)
    assert result.status_code==201
    assert approve(client,eid,original).status_code==412
    saved=client.get(f"/v1/encounters/{eid}/draft-proposals/{proposal.json()['id']}",headers=headers()).json()
    assert saved['stale'] is True
    assert saved['draft']==proposal.json()['draft']
