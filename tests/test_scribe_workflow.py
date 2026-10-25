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


def test_speaker_role_scoring_keeps_wrong_roles_and_missing_boundaries():
    from services.speaker_comparison import role_metrics
    ref=[{'start_ms':0,'end_ms':1000,'role':'patient'}]
    hyp=[{'start_ms':0,'end_ms':1000,'speaker_id':'channel_0'}]
    result=role_metrics(ref,hyp,{'channel_0':'clinician'})['patient']
    assert result['recall']==0 and result['missed_ms']==1000
    assert result['boundaries']['missed']==2


def test_boundary_matching_is_one_to_one_and_tolerance_bounded():
    from services.speaker_comparison import boundaries
    result=boundaries([0,1000],[100,120,1300])
    assert result['matched']==1 and result['missed']==1 and result['extra']==2


def test_reserved_cohort_leakage_is_rejected_before_network(tmp_path):
    import json
    from services.acceptance_audit import audit
    evaluation=tmp_path/'evaluation';(evaluation/'datasets'/'dev').mkdir(parents=True)
    (evaluation/'acceptance-reservation-v1.json').write_text(json.dumps({'reserved_groups':['held_out']}))
    (evaluation/'datasets'/'dev'/'manifest.json').write_text(json.dumps({'cases':[{'group_id':'held_out'}]}))
    with pytest.raises(ValueError,match='leakage'):audit(tmp_path,tmp_path/'out.json',fetch=False)


def test_diagnostic_alignment_matches_frozen_lexical_distance():
    import random
    from services.conversation_errors import alignment
    from services.evaluation import distance
    rng=random.Random(104)
    for _ in range(60):
        a,b=[rng.choices(['cough','fever','no','patient'],k=rng.randrange(15)) for _ in range(2)]
        assert len(alignment(a,b))==distance(a,b)


def test_channel_diagnostics_keep_original_turn_indices_and_overlap():
    from services.conversation_errors import analyze
    turns=[{'start_ms':0,'end_ms':1000,'role':'patient','reference':'Cough.'},
           {'start_ms':100,'end_ms':900,'role':'doctor','reference':'No fever.'}]
    result=analyze({'id':'synthetic','reference':'No fever.','hypothesis':'fever',
                    'normalized_edits':1,'failed':False},[turns[1]],turns)
    assert result['first_100_error_examples'][0]['reference_turn_index']==1
    assert result['errors_on_overlapping_reference_turns']==1
