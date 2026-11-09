import json,os,socket,subprocess,sys
from copy import deepcopy
from pathlib import Path
import pytest
from services.engineering_status import validate,sha256
from services.offline_preflight import check_baseline
from services.benchmark_integrity import replay
from services.detailed_benchmark import fast_score
from tests.test_foundation import setup


def test_task_count_and_evidence_are_tamper_checked(tmp_path):
    p=tmp_path/'proof.json';p.write_text('{}')
    doc={'total':1,'tasks':[{'id':'00-01','status':'verified','evidence':[{'path':'proof.json','sha256':sha256(p)}],'tests':['positive_and_negative'],'limitations':'Synthetic scope only'}]}
    assert validate(doc,tmp_path)['verified']==1
    p.write_text('{"changed":true}')
    with pytest.raises(ValueError):validate(doc,tmp_path)
    p.unlink()
    with pytest.raises(ValueError):validate(doc,tmp_path)
    changed=deepcopy(doc);changed['tasks'].append(changed['tasks'][0])
    with pytest.raises(ValueError):validate(changed,tmp_path)


def test_baseline_paths_and_model_directories_must_exist(tmp_path):
    p=tmp_path/'report.json';p.write_text('{}');(tmp_path/'models').mkdir()
    document={'benchmark_sha256':{'report.json':sha256(p)},'installed_model_directories':[{'path':'models'}]}
    assert check_baseline(document,tmp_path)['evidence_files_checked']==1
    p.write_text('corrupt')
    with pytest.raises(ValueError):check_baseline(document,tmp_path,require_local_models=True)
    document['benchmark_sha256']={};document['installed_model_directories']=[{'path':'absent'}]
    with pytest.raises(ValueError):check_baseline(document,tmp_path,require_local_models=True)
    assert check_baseline(document,tmp_path)['missing_local_model_directories']==['absent']


def test_full_baseline_inventory_has_no_missing_or_changed_paths():
    document=json.loads(Path('evaluation/reports/engineering-baseline.json').read_text(encoding='utf-8'))
    assert check_baseline(document)['evidence_files_checked']>=198


def test_offline_preflight_reports_cached_capabilities_without_install_or_network(tmp_path):
    from services.offline_preflight import inspect
    report = inspect(tmp_path, hash_models=True)
    assert report['schema_version'] == 'offline_preflight_v1'
    assert report['new_installations_attempted'] == 0
    assert report['external_calls_attempted'] == 0
    assert {'tools', 'node', 'npm_dependencies', 'python_wheelhouse', 'models', 'packages', 'config_sha256'} <= set(report)
    assert report['model_contents_hashed'] is True


def test_local_demo_launchers_are_isolated_and_loopback_bound():
    compose = Path('compose.yaml').read_text(encoding='utf-8')
    launcher = Path('scripts/start.ps1').read_text(encoding='utf-8')
    assert "127.0.0.1:8000:8000" in compose
    assert 'internal: true' in compose and 'read_only: true' in compose
    assert 'data/local-config.json' in launcher and 'services.launch' in launcher
    assert 'NoBrowser' in launcher and 'WithPostgres' in launcher


def test_offline_guard_denies_external_dns_tcp_udp_but_preserves_loopback():
    program='''
import socket
import services
from services.offline import OfflineNetworkDenied
for fn in [lambda:socket.getaddrinfo('example.com',443),lambda:socket.gethostbyname('example.com'),lambda:socket.socket().connect(('203.0.113.1',443)),lambda:socket.socket(socket.AF_INET,socket.SOCK_DGRAM).sendto(b'x',('203.0.113.1',53))]:
 try:fn()
 except OfflineNetworkDenied:pass
 else:raise AssertionError('External network was allowed')
assert socket.getaddrinfo('localhost',8010)
s=socket.socket();s.bind(('127.0.0.1',0));s.listen(1)
c=socket.socket();c.connect(s.getsockname());peer,_=s.accept();peer.close();c.close();s.close()
print('network_denial_and_loopback_pass')
'''
    result=subprocess.run([sys.executable,'-c',program],env={**os.environ,'MED_TRANSCRIPT_OFFLINE':'1'},capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr


def test_offline_guard_rejects_rebound_localhost():
    program='''
import socket
socket.getaddrinfo=lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('203.0.113.1',443))]
import services
from services.offline import OfflineNetworkDenied
try:socket.getaddrinfo('localhost',443)
except OfflineNetworkDenied:print('rebinding_denied')
else:raise AssertionError('DNS rebinding was accepted')
'''
    result=subprocess.run([sys.executable,'-c',program],env={**os.environ,'MED_TRANSCRIPT_OFFLINE':'1'},capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr


def test_strict_offline_profile_rejects_hosted_and_live_oauth(monkeypatch):
    from services.offline import validate_profile
    monkeypatch.setenv('MED_TRANSCRIPT_PROFILE','no_external_dependency')
    monkeypatch.setenv('MED_TRANSCRIPT_OFFLINE','0')
    with pytest.raises(ValueError):validate_profile()
    monkeypatch.setenv('MED_TRANSCRIPT_OFFLINE','1');monkeypatch.setenv('MED_TRANSCRIPT_AUTH_MODE','google')
    with pytest.raises(ValueError):validate_profile()
    monkeypatch.setenv('MED_TRANSCRIPT_AUTH_MODE','local');monkeypatch.setenv('MED_TRANSCRIPT_DRAFTING_MODE','hosted')
    with pytest.raises(ValueError):validate_profile()


def test_replay_rejects_score_reference_coverage_and_denominator_mutations():
    manifest={'cases':[{'group_id':'one','audio_sha256':'a'*64,'reference_turns':[{'reference':'No allergy.'}]}]}
    row={'id':'one','reference':'No allergy.','hypothesis':'No allergy.','input_sha256':'a'*64,'failed':False,'input_coverage_complete':True,**fast_score('No allergy.','No allergy.')}
    report={'cases':[row],'complete':True}
    assert replay(report,manifest)['completed_cases']==1
    for key,value in [('normalized_edits',1),('reference','Changed.'),('input_coverage_complete',False),('failed',True)]:
        bad=deepcopy(report);bad['cases'][0][key]=value
        with pytest.raises(ValueError):replay(bad,manifest)
    bad=deepcopy(report);bad['cases']=[]
    with pytest.raises(ValueError):replay(bad,manifest)


def test_audit_configuration_keeps_strict_third_party_checks():
    workflow=Path('.github/workflows/dependency-audit.yml').read_text()
    assert '--strict --skip-editable' in workflow
    assert 'pip install -c constraints-ci.txt -e ' in workflow
    assert '--ignore-vuln' not in workflow


def test_offline_scripted_workflow_blocks_dose_error_and_viewer_write(tmp_path,monkeypatch):
    monkeypatch.setenv('MED_TRANSCRIPT_AUTH_MODE','local');monkeypatch.setenv('MED_TRANSCRIPT_DRAFTING_MODE','deterministic')
    from services.offline_demo import prepare,walkthrough
    app,config=prepare(tmp_path/'isolated')
    result=walkthrough(app,config)
    assert result['synthetic_dose_error_blocked'] and result['viewer_write_denied']
    assert result['corrected_version_approved'] and len(result['exports'])==4
    assert set(result['stage_latency']['stages']) == {'recording','transfer','normalization','asr','diarization','extraction','drafting','verification','clinician_review','export'}
    assert result['stage_latency']['stages']['recording']['status']=='unavailable'
    assert result['stage_latency']['complete'] is False
    with pytest.raises(FileExistsError):prepare(tmp_path/'isolated')


def test_release_dimensions_cannot_collapse_or_promote_synthetic_evidence():
    from services.release_policy import validate_matrix,engineering_gate
    matrix={'offline_demo':'verified','engineering_verified':'not_established','research_evidence_complete':'not_established','clinical_approved':'BLOCKED_EXTERNAL_EVIDENCE_REQUIRED'}
    assert validate_matrix(matrix)==matrix
    with pytest.raises(ValueError):validate_matrix({'ready':True})
    with pytest.raises(ValueError):validate_matrix({**matrix,'clinical_approved':'verified'})
    assert engineering_gate([{'code':'corrupted_evidence','severity':'P2'}])['status']=='blocked'
    assert engineering_gate([])['status']=='not_established'


def test_english_only_schema_rejects_other_languages_and_imaging(setup):
    from tests.test_foundation import headers,payload
    client,_,_=setup
    assert client.post('/v1/encounters',headers=headers(),json=payload()).status_code==201
    for key,value in [('language','fr'),('workflow','MRI'),('synthetic_data',False)]:
        assert client.post('/v1/encounters',headers=headers(),json={**payload(),key:value}).status_code==422


def test_secret_scanner_redacts_values_and_accepts_placeholders():
    from services.secret_scan import inspect_text
    secret='zY9x'*10
    text='access_key = "'+secret+'"\n'+('AKIA'+'Z'*16)
    results=inspect_text(text,'sample.py',[secret])
    assert {r['type'] for r in results}>={'assigned_secret','aws_access_key','known_local_credential'}
    assert secret not in json.dumps(results)
    assert not inspect_text('api_key = "REPLACE_WITH_A_FAKE_PLACEHOLDER"','example.env')
    assert inspect_text('-----BEGIN '+'PRIVATE KEY-----','private.pem')[0]['type']=='private_key_material'


def test_lower_evidence_tiers_cannot_claim_independent_gold():
    from services.release_policy import validate_evidence_scope
    assert validate_evidence_scope({'independent_clinical_gold':False,'real_patient_release_authorized':False},'developer_synthetic_oracles')
    with pytest.raises(ValueError):validate_evidence_scope({'independent_clinical_gold':True,'real_patient_release_authorized':False},'model_judgments')


def test_negative_index_retains_failures_without_misclassifying_clinical_release(tmp_path):
    from services.negative_index import build,reasons
    p=tmp_path/'failed.json';p.write_text(json.dumps({'complete':False,'cases':[{'failed':True}],'real_patient_release_authorized':False}))
    baseline={'source_commit':'snapshot','benchmark_sha256':{'failed.json':sha256(p)}}
    index=build(baseline,tmp_path)
    assert len(index['entries'])==1 and index['entries'][0]['sha256']==sha256(p)
    assert not reasons({'real_patient_release_authorized':False,'complete':True,'failed_cases':0})
    p.write_text('{}')
    with pytest.raises(ValueError):build(baseline,tmp_path)


def test_existing_hosted_ci_receipt_requires_exact_commit_and_all_jobs():
    from services.engineering_status import verify_ci_receipt
    receipt=json.loads(Path('evaluation/reports/hosted-ci-baseline-receipt.json').read_text())
    assert verify_ci_receipt(receipt,'c1afa1e70277af0942c389a37a2cfdf4096c9cc0')['jobs_verified']==5
    bad=deepcopy(receipt);bad['jobs']=bad['jobs'][:-1]
    with pytest.raises(ValueError):verify_ci_receipt(bad,receipt['source_commit'])
    bad=deepcopy(receipt);bad['jobs'][0]['conclusion']='failure'
    with pytest.raises(ValueError):verify_ci_receipt(bad,receipt['source_commit'])
    with pytest.raises(ValueError):verify_ci_receipt(receipt,'wrong-commit')
