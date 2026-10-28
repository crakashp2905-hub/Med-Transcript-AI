from collections import Counter
import json
from pathlib import Path
import re
from uuid import uuid4

from services.api.ingest import run_once
from services.review.clinical_models import RuleExtractor
from services.review.models import Fact
from tests.test_foundation import setup,headers,queue_upload


def test_scoped_source_batches_preserve_full_version_binding_and_unselected_segments(setup):
    client,db,_=setup;eid,upload,_,_=queue_upload(client)
    assert run_once(db,Path(db).parent/'assets')['status']=='succeeded'
    response=client.post(f'/v1/encounters/{eid}/manual-transcripts',headers=headers(),json={'audio_asset_id':upload['id'],
        'segments':[{'start_ms':i*4,'end_ms':i*4+4,'text':f'Patient reports cough {i}.','role':'patient'} for i in range(24)]})
    assert response.status_code==201,response.text
    tx=response.json();ids=[s['segment_id'] for s in tx['segments']];url=f'/v1/encounters/{eid}/fact-proposals'
    body={'transcript_version_id':tx['id'],'segment_ids':ids[:20]}
    response=client.post(url,headers=headers(),json=body);assert response.status_code==201,response.text
    value=response.json();assert value['transcript_version_id']==tx['id']
    assert value['source_batch']['unselected_segment_ids']==ids[20:]
    assert {f['evidence']['segment_id'] for f in value['facts']}==set(ids[:20])
    assert all(not f['reviewed'] for f in value['facts'])
    assert client.post(url,headers=headers('b'*40),json=body).status_code==404
    for invalid in ([str(uuid4())],[ids[0],ids[0]],ids[:21]):
        assert client.post(url,headers=headers(),json={**body,'segment_ids':invalid}).status_code==422
    assert client.get(f'/v1/encounters/{eid}/workspace',headers=headers()).json()['note'] is None


def test_detailed_302_span_case_fits_bounded_batches_without_silent_source_loss():
    manifest=json.loads(Path('evaluation/datasets/meddistract-detailed-v1/manifest.json').read_text())
    case=next(c for c in manifest['cases'] if c['group_id']=='day1_consultation07__clean')
    segments=[{'segment_id':str(uuid4()),'text':re.sub(r'<[^>]+>','',t['reference'])} for t in case['reference_turns']]
    provider=RuleExtractor();complete=provider.extract_facts({'segments':segments},authorized=True,synthetic=True)['facts']
    batched=[]
    for start in range(0,len(segments),20):
        facts=provider.extract_facts({'segments':segments[start:start+20]},authorized=True,synthetic=True)['facts']
        assert len(facts)<=300
        for fact in facts:Fact.model_validate(fact)
        batched.extend(facts)
    def evidence(facts):return Counter((f['evidence']['segment_id'],f['evidence']['start_char'],f['evidence']['end_char'],f['evidence']['quote']) for f in facts)
    assert len(complete)==302 and evidence(batched)==evidence(complete)
    assert all(not f['reviewed'] and not f['critical_reviewed'] for f in batched)
