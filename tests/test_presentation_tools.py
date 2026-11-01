import base64
import hashlib
import json
from tests.test_foundation import setup, headers
from tests.test_review_workflow import prepare, draft, approve


def test_fhir_export_requires_real_approval_and_preserves_evidence(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path)
    note=draft(client,eid,tx,facts)['note']
    from uuid import uuid4
    assert client.post(f'/v1/encounters/{eid}/exports',headers=headers(),json={'approval_id':str(uuid4()),'format':'fhir'}).status_code==404
    approval=approve(client,eid,note).json()
    result=client.post(f'/v1/encounters/{eid}/exports',headers=headers(),json={'approval_id':approval['id'],'format':'fhir'})
    assert result.status_code==201,result.text
    receipt=result.json()
    artifact=client.get(receipt['download_url'],headers=headers())
    assert hashlib.sha256(artifact.content).hexdigest()==receipt['sha256']
    resource=artifact.json()
    assert resource['resourceType']=='DocumentReference'
    assert resource['docStatus']=='final'
    inner=json.loads(base64.b64decode(resource['content'][0]['attachment']['data']))
    assert inner['note']=={k:v for k,v in note.items() if k!='sha256'}
    assert inner['approval']==approval
    assert inner['note']['facts'][0]['evidence']==facts[0]['evidence']
    assert client.get(receipt['download_url'],headers=headers('b'*40)).status_code==404
    again=client.post(f'/v1/encounters/{eid}/exports',headers=headers(),json={'approval_id':approval['id'],'format':'fhir'})
    assert again.json()==receipt


def test_study_dashboard_is_authenticated_and_explicit_about_validation(setup):
    client,_,_=setup
    assert client.get('/v1/study-dashboard').status_code==401
    result=client.get('/v1/study-dashboard',headers=headers())
    assert result.status_code==200
    value=result.json()
    assert value['clinical_validation'] is False
    assert value['hardware_cost'] is None
    assert 'reports' in value


def test_public_demo_does_not_accept_paths_or_unlisted_sources(setup):
    client,_,_=setup
    assert client.get('/v1/demo-cases').status_code==401
    assert client.post('/v1/demo?public_case=../../local-config.json',headers=headers()).status_code==422
    from services.review.presentation import public_demo
    import pytest
    with pytest.raises(ValueError):
        public_demo('../local-config.json')

def test_dashboard_prefers_final_and_never_scores_partial_experiments(tmp_path):
    from services.review.presentation import campaign_evidence
    root=tmp_path/'reports';root.mkdir()
    runs=tmp_path/'runs/meddistract-detailed-v2';runs.mkdir(parents=True)
    (root/'detailed-ranking-v2-2026-10-29.json').write_text(json.dumps({'complete':False}))
    final=root/'detailed-ranking-final-2026-10-29.json'
    final.write_text(json.dumps({'complete':True}))
    partial={'candidate_id':'model','mode':'context','complete':False,'cases':[{'id':'one'}],
             'conditions':{'clean':{'normalized_wer':0}}}
    (runs/'model.context.json').write_text(json.dumps(partial))
    value=campaign_evidence(root)
    assert value['reports']['ranking']['complete'] is True
    assert value['sources']['ranking']['sha256']==hashlib.sha256(final.read_bytes()).hexdigest()
    assert value['experiments'][0]['status']=='incomplete'
    assert value['experiments'][0]['completed_cases']==1
    assert value['experiments'][0]['conditions'] is None
    final.unlink()
    assert campaign_evidence(root)['reports']['ranking']['complete'] is False


def test_missing_dashboard_evidence_is_not_reported_as_completed(tmp_path):
    from services.review.presentation import campaign_evidence
    value=campaign_evidence(tmp_path)
    assert value['reports']=={'ranking':None,'drafting':None,'execution':None,'recovery':None}
    assert value['sources']=={} and value['experiments']==[]
    assert value['clinical_validation'] is False
