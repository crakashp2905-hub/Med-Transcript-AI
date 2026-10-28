import copy
import json
from uuid import uuid4
import pytest

from services.review.clinical import check_claim,extract
from services.review.clinical_models import LocalClinicalModels,Extraction,Verdicts
from services.usability_metrics import correction
from tests.test_foundation import setup,headers
from tests.test_review_workflow import prepare,draft


@pytest.mark.parametrize('source,claim,code',[
    ('Taking metformin 500 mg and warfarin 5 mg.','Taking metformin 5 mg and warfarin 500 mg.','medication_dose_assignment_disagreement'),
    ('Patient denies fever but reports cough.','Patient reports fever but denies cough.','negation_scope_disagreement'),
    ('Patient reports cough and fever.','Patient reports cough.','omitted_source_terms'),
    ('Taking insulin 5 units.','Taking insulin 5 mg.','dose_or_unit_disagreement')])
def test_critical_scope_assignment_and_omission(source,claim,code):
    assert code in {f['code'] for f in check_claim(source,claim)}


@pytest.mark.parametrize('source,claim',[
    ('Taking metformin 1000 mg.','Taking metformin 1 g.'),
    ('Taking warfarin .005 g.','Taking warfarin 5 mg.')])
def test_exact_mass_conversion_does_not_create_a_false_dose_error(source,claim):
    assert check_claim(source,claim)==[]


def test_atomic_extraction_preserves_decimal_offsets_and_multiple_assertions():
    text='Taking metformin 0.5 g and warfarin 5 mg. Patient denies fever but reports cough.'
    facts=extract({'segments':[{'segment_id':str(uuid4()),'text':text}]})
    assert len(facts)==4
    assert facts[0]['dose_value']=='0.5' and facts[0]['dose_unit']=='g'
    assert facts[1]['medication_name']=='warfarin'
    assert facts[2]['assertion']=='negated' and facts[3]['assertion']=='affirmed'
    for f in facts:
        e=f['evidence'];assert text[e['start_char']:e['end_char']]==e['quote']==f['text']
        assert not f['reviewed'] and not f['critical_reviewed']


def test_partial_noncritical_source_span_cannot_hide_an_omitted_symptom(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path,'Patient reports cough. Patient reports fever.')
    result=draft(client,eid,tx,[facts[0]])
    assert any(f['code']=='unaccounted_source_content' for f in result['verification']['findings'])
    assert result['verification']['gate']=='blocked'


def test_structured_dose_cannot_disagree_with_unchanged_source_text(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path,'Taking warfarin 5 mg.')
    facts[0].update(dose_value='50',dose_unit='mg')
    result=draft(client,eid,tx,facts)
    assert any(f['code']=='structured_field_disagreement' for f in result['verification']['findings'])


@pytest.mark.parametrize('text,patch',[('Patient denies fever.',{'assertion':'affirmed'}),
    ('Previously stopped metformin.',{'temporality':'current'}),('Mother has diabetes.',{'subject':'patient'})])
def test_structured_polarity_time_and_subject_cannot_override_evidence(setup,text,patch):
    client,path,_=setup
    eid,tx,facts=prepare(client,path,text)
    facts[0].update(patch)
    result=draft(client,eid,tx,facts)
    assert any(f['code']=='structured_field_disagreement' for f in result['verification']['findings'])


def test_version_comparison_is_scoped_and_includes_structured_changes(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path,'Taking warfarin 5 mg.')
    first=draft(client,eid,tx,facts)['note']
    facts[0]['dose_value']='50'
    second=client.patch(f"/v1/encounters/{eid}/notes/{first['id']}",headers={**headers(),'If-Match':f'"{first["sha256"]}"'},json={'transcript_version_id':tx['id'],'facts':facts}).json()['note']
    route=f"/v1/encounters/{eid}/notes/{first['id']}/compare/{second['id']}"
    comparison=client.get(route,headers=headers()).json()
    assert comparison['changes'][0]['changed_fields']==['dose_value']
    assert client.get(route,headers=headers('b'*40)).status_code==404
    assert len(client.get(f'/v1/encounters/{eid}/versions',headers=headers()).json()['notes'])==2
    assert client.get(f'/v1/encounters/{eid}/versions',headers=headers('b'*40)).status_code==404


def test_timing_retry_creates_one_session_and_history_contains_no_note_text(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path)
    note=draft(client,eid,tx,facts)['note']
    base=f'/v1/encounters/{eid}/review-sessions'
    body={'note_version_id':note['id'],'client_request_id':str(uuid4())}
    first=client.post(base,headers=headers(),json=body)
    assert first.status_code==201
    assert client.post(base,headers=headers(),json=body).json()==first.json()
    result=client.get(base,headers=headers()).json()
    assert len(result['items'])==1 and 'cough' not in json.dumps(result)
    assert client.get(base,headers=headers('b'*40)).status_code==404
    assert correction('word '*20000,'word '*19999+'changed',10)['word_edits']==1


def test_timed_review_retains_selected_arm_and_rejects_relabelling_retry(setup):
    client,path,_=setup;eid,tx,facts=prepare(client,path);note=draft(client,eid,tx,facts)['note']
    base=f'/v1/encounters/{eid}/review-sessions';body={'note_version_id':note['id'],'client_request_id':str(uuid4()),'drafting_arm':'deterministic'}
    session=client.post(base,headers=headers(),json=body)
    assert session.status_code==201
    assert client.post(base,headers=headers(),json={**body,'drafting_arm':'local_qwen'}).status_code==409
    measured=client.post(base+'/'+session.json()['id']+'/complete',headers=headers(),json={'note_version_id':note['id']})
    assert measured.status_code==200 and measured.json()['drafting_arm']=='deterministic'
    assert measured.json()['arm_attribution']=='clinician_selected_not_independently_verified'
    assert measured.json()['active_time_verified'] is False


def test_timing_captures_structured_edits_and_rejects_conflicting_replay(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path,'Taking warfarin 5 mg.')
    first=draft(client,eid,tx,facts)['note']
    base=f'/v1/encounters/{eid}/review-sessions'
    session=client.post(base,headers=headers(),json={'note_version_id':first['id']}).json()
    facts[0]['dose_value']='50'
    second=client.patch(f"/v1/encounters/{eid}/notes/{first['id']}",headers={**headers(),'If-Match':f'"{first["sha256"]}"'},json={'transcript_version_id':tx['id'],'facts':facts}).json()['note']
    route=base+'/'+session['id']+'/complete'
    body={'note_version_id':second['id']}
    response=client.post(route,headers=headers(),json=body)
    assert response.status_code==200,response.text
    assert response.json()['word_edits']==0 and response.json()['field_edit_counts']['dose_value']==1
    assert client.post(route,headers=headers(),json={'note_version_id':first['id']}).status_code==409


def test_semantic_model_cannot_change_saved_verification(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path,'Taking warfarin 5 mg.')
    facts[0]['text']='Taking warfarin 50 mg.'
    saved=draft(client,eid,tx,facts)
    class Fake:
        def check_claims(self,claims,**kwargs):
            return {'verdicts':[{'fact_id':c['fact_id'],'label':'supported'} for c in claims],
                'cannot_clear_existing_findings':True}
    client.app.state.clinical_models=Fake()
    response=client.post(f'/v1/encounters/{eid}/semantic-checks',headers=headers(),json={'note_version_id':saved['note']['id']})
    assert response.status_code==201,response.text
    ws=client.get(f'/v1/encounters/{eid}/workspace',headers=headers()).json()
    assert ws['verification']['id']==saved['verification']['id']
    assert ws['verification']['gate']=='blocked'


def test_model_fact_citations_reject_hallucinations_and_stay_unreviewed():
    sid=str(uuid4());tx={'segments':[{'segment_id':sid,'text':'No fever.'}]}
    class Fake(LocalClinicalModels):
        def complete(self,*args):
            return Extraction.model_validate({'facts':[{'segment_id':sid,'quote':self.quote,'category':'symptom','section':'subjective'}]}),{}
    provider=Fake();provider.quote='No fever.'
    result=provider.extract_facts(tx,authorized=True,synthetic=True)
    assert not result['facts'][0]['reviewed']
    provider.quote='Diabetes diagnosed.'
    with pytest.raises(ValueError,match='absent or ambiguous'):
        provider.extract_facts(tx,authorized=True,synthetic=True)


def test_supportive_model_cannot_clear_a_dose_rule():
    fid=str(uuid4())
    class Fake(LocalClinicalModels):
        def complete(self,*args):
            return Verdicts.model_validate({'verdicts':[{'fact_id':fid,'label':'supported','evidence_quote':'5 mg','reason':'Synthetic deliberately incorrect model verdict'}]}),{}
    result=Fake().check_claims([{'fact_id':fid,'text':'Taking warfarin 50 mg.','evidence':'Taking warfarin 5 mg.'}],authorized=True,synthetic=True)
    assert result['verdicts'][0]['requires_review']
    assert result['cannot_clear_existing_findings']


def test_rule_fact_proposals_are_separate_and_clinical_models_default_disabled(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path)
    base=f'/v1/encounters/{eid}'
    result=client.post(base+'/fact-proposals',headers=headers(),json={'transcript_version_id':tx['id']})
    assert result.status_code==201,result.text
    assert not result.json()['facts'][0]['reviewed']
    assert client.get(base+'/workspace',headers=headers()).json()['note'] is None
    route=base+'/clinical-proposals/'+result.json()['id']
    assert client.get(route,headers=headers()).status_code==200
    assert client.get(route,headers=headers('b'*40)).status_code==404
    assert client.post(base+'/fact-proposals',headers=headers(),json={'transcript_version_id':tx['id'],'mode':'local_model'}).status_code==422


def test_revocation_during_model_extraction_discards_output(setup):
    import sqlite3
    from services.review.clinical_models import RuleExtractor
    client,path,_=setup
    eid,tx,_=prepare(client,path)
    class Revoking:
        def extract_facts(self,tx,**kwargs):
            with sqlite3.connect(path) as con:
                con.execute("UPDATE authorizations SET withdrawn_at='2026-01-01T00:00:00+00:00' WHERE encounter=?",(eid,))
            return RuleExtractor().extract_facts(tx,**kwargs)
    client.app.state.clinical_models=Revoking()
    r=client.post(f'/v1/encounters/{eid}/fact-proposals',headers=headers(),json={'transcript_version_id':tx['id'],'mode':'local_model'})
    assert r.status_code==403
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM model_proposals WHERE kind='fact_proposal'").fetchone()[0]==0


def test_model_transport_constrains_input_quotes_and_verifies_digest(monkeypatch):
    import io
    import urllib.request
    from services.review.clinical_models import MODEL_DIGESTS
    sid=str(uuid4());posts=[]
    class Opener:
        def open(self,request,**kwargs):
            if isinstance(request,str):
                value={'models':[{'name':'qwen2.5:1.5b','digest':MODEL_DIGESTS['qwen2.5:1.5b']}]} if request.endswith('/tags') else {'version':'test-runtime'}
            else:
                payload=json.loads(request.data);posts.append(payload)
                props=payload['response_format']['json_schema']['schema']['$defs']['SelectedFact']['properties']
                assert props['segment_id']['enum']==[sid]
                assert props['quote']['enum']==['Taking warfarin 5 mg.','Patient denies fever.']
                content={'facts':[{'segment_id':sid,'quote':'Taking warfarin 5 mg.','category':'medication','section':'subjective','assertion':'affirmed'}]}
                value={'choices':[{'message':{'content':json.dumps(content)}}],'usage':{'prompt_tokens':7,'api_key':'must-not-persist'}}
            return io.BytesIO(json.dumps(value).encode())
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    result=LocalClinicalModels(True).extract_facts({'segments':[{'segment_id':sid,'text':'Taking warfarin 5 mg. Patient denies fever.'}]},authorized=True,synthetic=True)
    assert len(posts)==1
    assert result['provenance']['usage']=={'prompt_tokens':7}
    assert result['provenance']['model_digest']==MODEL_DIGESTS['qwen2.5:1.5b']
    assert not result['facts'][0]['reviewed']


def test_changed_model_digest_prevents_inference(monkeypatch):
    import io
    import urllib.request
    class Opener:
        def open(self,request,**kwargs):
            assert isinstance(request,str) and request.endswith('/tags')
            return io.BytesIO(json.dumps({'models':[{'name':'qwen2.5:1.5b','digest':'changed'}]}).encode())
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    with pytest.raises(ValueError,match='model_digest_mismatch'):
        LocalClinicalModels(True).extract_facts({'segments':[{'segment_id':str(uuid4()),'text':'No fever.'}]},authorized=True,synthetic=True)
