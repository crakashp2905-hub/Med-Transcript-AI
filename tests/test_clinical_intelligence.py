import json
import random
from pathlib import Path
from uuid import uuid4

import pytest

from services.clinical_metrics import character_distance, coverage, evaluate
from services.evaluation import distance
from services.review.clinical import check_claim, extract
from services.review.providers import DeterministicProvider, JSONProvider, validate
from services.diarization import confirm_roles, diarize
from services.usability_metrics import correction, summarize_runs
from tests.test_foundation import setup, headers
from tests.test_review_workflow import prepare


def test_exact_long_character_metric_matches_small_dynamic_program():
    rng = random.Random(19)
    for _ in range(100):
        a,b = [''.join(rng.choices('abc ',k=rng.randrange(20))) for _ in range(2)]
        assert character_distance(a,b) == distance(a,b)
    assert character_distance('a'*30000,'a'*29999+'b') == 1


def test_concept_omissions_insertions_failures_and_overlap_coverage():
    gold = {"category":"dose","concept":"warfarin 5 mg","subject":"patient","assertion":"affirmed","temporality":"current"}
    wrong = {**gold,"concept":"warfarin 50 mg"}
    result = evaluate('Take 5 mg','Take 50 mg',[gold],[wrong])
    assert result['concept_omissions'] == result['concept_insertions'] == 1
    assert result['by_category']['dose']['true_positive'] == 0
    assert evaluate('Take 5 mg','anything',[gold],[gold],failed=True)['concept_recall'] == 0
    assert coverage([(0,60),(40,90)],100)['covered_ms'] == 90


def test_independent_synthetic_adversarial_labels():
    body = json.loads((Path(__file__).resolve().parents[1]/'evaluation/clinical-adversarial-v1.json').read_text())
    for case in body['cases']:
        assert bool(check_claim(case['source'],case['claim'])) == case['expected_unsafe'], case['id']


def test_multiple_evidence_spans_remain_exact_and_unreviewed():
    text='No fever. Taking warfarin 0.5 mg.'
    facts=extract({'segments':[{'segment_id':str(uuid4()),'text':text}]})
    assert len(facts)==2
    for fact in facts:
        e=fact['evidence']
        assert text[e['start_char']:e['end_char']]==e['quote']
        assert not fact['reviewed'] and fact['subject']=='unknown'


def test_providers_cannot_enable_disclosure_or_invent_citations():
    with pytest.raises(ValueError):
        JSONProvider('https://example.com','test',mode='hosted',enabled=True).draft([],authorized=True,synthetic=False)
    with pytest.raises(ValueError):
        JSONProvider('http://localhost','test').draft([],authorized=True,synthetic=True)
    with pytest.raises(ValueError):
        validate({'statements':[{'section':'plan','text':'Invented treatment','fact_ids':['fake']}]},[])
    assert 'secret-value' not in repr(JSONProvider('http://localhost','test',api_key='secret-value'))


def test_diarization_never_assigns_roles_without_explicit_confirmation():
    with pytest.raises(ValueError):
        diarize('unused',{'enabled':False})
    rows=[{'speaker_id':'s1','role':'unknown'}]
    with pytest.raises(ValueError):
        confirm_roles(rows,{'s1':'patient'})
    assert confirm_roles(rows,{'s1':'patient'},clinician_confirmed=True)[0]['role']=='patient'


def test_diarization_scoring_counts_misses_false_alarms_and_confusion():
    from services.diarization_evaluation import score_turns
    reference=[{'start_ms':0,'end_ms':1000,'role':'patient'}, {'start_ms':1000,'end_ms':2000,'role':'clinician'}]
    predicted=[{'start_ms':0,'end_ms':1000,'speaker_id':'a'},{'start_ms':1000,'end_ms':2000,'speaker_id':'b'}]
    assert score_turns(reference,predicted)['diarization_error_rate']==0
    assert score_turns(reference,[])['diarization_error_rate']==1
    predicted[1]['speaker_id']='a'
    assert score_turns(reference,predicted)['confused_speaker_ms']==1000


def test_speaker_projection_keeps_boundary_crossings_unknown():
    from services.diarization import attach_speakers
    tx={'segments':[{'start_ms':0,'end_ms':1000,'speaker_id':None,'uncertainties':[]}],'review_flags':[]}
    report={'segments':[{'start_ms':0,'end_ms':900,'speaker_id':'a'},{'start_ms':900,'end_ms':1000,'speaker_id':'b'}]}
    assert attach_speakers(tx,report)['segments'][0]['speaker_id'] is None


def test_public_model_download_budget_preserves_existing_target(tmp_path,monkeypatch):
    import io
    import urllib.request
    from services.provision_public_diarization import fetch
    target=tmp_path/'model.onnx';target.write_bytes(b'known valid model')
    monkeypatch.setattr(urllib.request,'urlopen',lambda *a,**kw:io.BytesIO(b'x'*100))
    with pytest.raises(ValueError,match='size budget'):
        fetch('https://example.invalid/model',target,maximum=10)
    assert target.read_bytes()==b'known valid model'
    assert not list(tmp_path.glob('*.partial'))


def test_measured_review_and_latency_do_not_fabricate_cost_or_active_time():
    result=correction('5 mg','50 mg',1000,500)
    assert result['word_edits']==1 and not result['active_time_verified']
    with pytest.raises(ValueError):
        correction('a','b',100,101)
    assert summarize_runs([{'wall_seconds':1},{'wall_seconds':3}])['cost_total'] is None


def test_proposal_is_separate_and_not_an_approvable_note(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path)
    response=client.post(f'/v1/encounters/{eid}/draft-proposals',headers=headers(),json={'transcript_version_id':tx['id'],'facts':facts})
    assert response.status_code==201,response.text
    assert response.json()['status']=='unreviewed_proposal_not_approvable'
    assert client.get(f'/v1/encounters/{eid}/workspace',headers=headers()).json()['note'] is None
    route=f"/v1/encounters/{eid}/draft-proposals/{response.json()['id']}"
    assert client.get(route,headers=headers()).json()['stale'] is False
    assert client.get(route,headers=headers('b'*40)).status_code==404


def test_proposal_and_review_metrics_immutable_and_purged(setup):
    import sqlite3
    from services.api.storage import Store
    from services.maintenance import purge
    from tests.test_review_workflow import draft
    client,path,_=setup
    eid,tx,facts=prepare(client,path)
    assert client.post(f'/v1/encounters/{eid}/draft-proposals',headers=headers(),json={
        'transcript_version_id':tx['id'],'facts':facts}).status_code==201
    note=draft(client,eid,tx,facts)['note']
    session=client.post(f'/v1/encounters/{eid}/review-sessions',headers=headers(),json={'note_version_id':note['id']}).json()
    assert client.post(f"/v1/encounters/{eid}/review-sessions/{session['id']}/complete",headers=headers(),json={'note_version_id':note['id']}).status_code==200
    for table in ('model_proposals','review_metrics'):
        with pytest.raises(sqlite3.IntegrityError,match='immutable'):
            with Store(path).transaction() as con:
                con.execute(f"UPDATE {table} SET body='{{}}' WHERE encounter=?",(eid,))
    assert client.post(f'/v1/encounters/{eid}/deletion-requests',headers=headers()).status_code==202
    assert purge(path,str(Path(path).parent/'assets'))['requests'][0]['status']=='primary_purged_backups_pending'
    with Store(path).transaction() as con:
        for table in ('model_proposals','review_metrics'):
            assert con.execute(f'SELECT COUNT(*) FROM {table} WHERE encounter=?',(eid,)).fetchone()[0]==0


def test_full_consultation_manifest_lock_and_reference_bounds():
    import hashlib
    root=Path('evaluation/datasets/primock57-full-v1')
    raw=(root/'manifest.json').read_bytes()
    lock=json.loads((root/'lock.json').read_text())
    manifest=json.loads(raw)
    assert hashlib.sha256(raw).hexdigest()==lock['manifest_sha256']
    assert len(manifest['cases'])==3
    assert sum(c['duration_ms'] for c in manifest['cases'])==1899600
    for case in manifest['cases']:
        assert 300000<=case['duration_ms']<=1800000
        for turn in case['reference_turns']:
            assert 0<=turn['start_ms']<turn['end_ms']<=case['duration_ms']


def test_adversarial_report_rebuild():
    from services.clinical_evaluation import adversarial
    saved=json.loads(Path('evaluation/reports/clinical-adversarial-v2-2026-10-25.json').read_text())
    assert adversarial('evaluation/clinical-adversarial-v1.json')==saved


def test_semantic_dose_change_blocks_even_with_plausible_quote_and_reason(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path,'Taking warfarin 5 mg.')
    facts[0].update(text='Taking warfarin 50 mg.',clarification='A long explanation cannot erase a definite source contradiction.')
    response=client.post(f'/v1/encounters/{eid}/drafts',headers=headers(),json={'transcript_version_id':tx['id'],'facts':facts})
    assert response.status_code==201
    assert any(f['code']=='dose_or_unit_disagreement' for f in response.json()['verification']['findings'])


def test_review_session_reports_counts_and_is_idempotent_and_scoped(setup):
    from tests.test_review_workflow import draft
    client,path,_=setup
    eid,tx,facts=prepare(client,path)
    note=draft(client,eid,tx,facts)['note']
    start=client.post(f'/v1/encounters/{eid}/review-sessions',headers=headers(),json={'note_version_id':note['id']})
    assert start.status_code==201,start.text
    route=f"/v1/encounters/{eid}/review-sessions/{start.json()['id']}/complete"
    body={'note_version_id':note['id'],'self_reported_active_ms':0}
    end=client.post(route,headers=headers(),json=body)
    assert end.status_code==200,end.text
    assert end.json()['word_edits']==0 and not end.json()['raw_text_in_telemetry']
    assert client.post(route,headers=headers(),json=body).json()==end.json()
    assert client.post(route,headers=headers('b'*40),json=body).status_code==404


def test_hosted_proposal_rejects_fully_local_encounter_before_network(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path)
    client.app.state.drafting_provider=JSONProvider('https://example.com','test',mode='hosted',enabled=True)
    response=client.post(f'/v1/encounters/{eid}/draft-proposals',headers=headers(),json={
        'transcript_version_id':tx['id'],'facts':facts,'hosted_text_disclosure_accepted':True})
    assert response.status_code==422


def test_revocation_during_drafting_discards_the_output(setup):
    import sqlite3
    client,path,_=setup
    eid,tx,facts=prepare(client,path)
    class RevokingProvider:
        def draft(self,facts,**kwargs):
            with sqlite3.connect(path) as con:
                con.execute("UPDATE authorizations SET withdrawn_at='2026-01-01T00:00:00+00:00' WHERE encounter=?",(eid,))
            return DeterministicProvider().draft(facts,**kwargs)
    client.app.state.drafting_provider=RevokingProvider()
    response=client.post(f'/v1/encounters/{eid}/draft-proposals',headers=headers(),json={'transcript_version_id':tx['id'],'facts':facts})
    assert response.status_code==403
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM model_proposals WHERE kind='draft_proposal'").fetchone()[0]==0


def test_local_json_provider_uses_bounded_transport_and_safe_usage():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    fact={'fact_id':'one','section':'subjective','text':'No fever.','reviewed':True}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert request['max_tokens']==2048
            answer={'choices':[{'message':{'content':json.dumps({'statements':[{'section':'subjective','text':'No fever.','fact_ids':['one']}]})}}],
                'usage':{'prompt_tokens':12,'api_key':'must-not-persist'}}
            raw=json.dumps(answer).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        provider=JSONProvider(f'http://127.0.0.1:{server.server_port}/draft','fake-test-server',enabled=True)
        result=provider.draft([fact],authorized=True,synthetic=True)
        assert result['provenance']['usage']=={'prompt_tokens':12}
        assert result['status']=='review_required'
    finally:
        server.shutdown();server.server_close();thread.join()
