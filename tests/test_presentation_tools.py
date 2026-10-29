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
