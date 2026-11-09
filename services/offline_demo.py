"""Isolated account-free model-free demonstration; synthetic software evidence only."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import secrets
import wave
from uuid import uuid4

from services.api.main import create_app, Identity
from services.engineering_status import sha256


def prepare(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    # Silence is a transport fixture, not speech or an ASR accuracy example.
    with wave.open(str(root/'demo-sample.wav'), 'wb') as target:
        target.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        target.writeframes(b'\0\0'*32000)
    source = {'fixture_id': 'developer_scripted_non_speech_workflow_v1', 'synthetic': True,
              'limitations': 'Silent transport fixture with developer-scripted reference text; not ASR output or human clinical gold.',
              'segments': [{'start_ms': 0, 'end_ms': 1000, 'role': 'patient', 'text': 'Patient takes warfarin 0.5 mg daily.'},
                           {'start_ms': 1000, 'end_ms': 2000, 'role': 'patient', 'text': 'Patient denies fever.'}]}
    (root/'demo-sample.json').write_text(json.dumps(source), encoding='utf-8')
    clinician_key, viewer_key = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    tenant, clinician = uuid4(), uuid4()
    config = {'clinician_key': clinician_key, 'viewer_key': viewer_key,
              'tenant_id': str(tenant), 'clinician_id': str(clinician), 'scope': source['limitations']}
    path = root/'access.json'
    path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    path.chmod(0o600)
    app = create_app(str(root/'demo.sqlite3'), {
        clinician_key: Identity(tenant_id=tenant, clinician_id=clinician),
        viewer_key: Identity(tenant_id=tenant, clinician_id=clinician, role='viewer')}, str(root/'assets'))
    return app, config


def walkthrough(app, config):
    from fastapi.testclient import TestClient
    from services.stage_timing import StageTimer
    client = TestClient(app)
    timing = StageTimer()
    timing.mark_unavailable('recording', 'silent_fixture_no_microphone')
    timing.mark_unavailable('asr', 'scripted_demo_no_asr')
    timing.mark_unavailable('diarization', 'single_scripted_role')
    headers = {'Authorization': 'Bearer '+config['clinician_key']}
    def require(response, expected):
        if response.status_code != expected:
            raise ValueError(f'offline_workflow_unexpected_status_{response.status_code}')
        return response.json()
    eid = timing.measure('transfer', lambda: require(client.post('/v1/demo', headers=headers), 201)['encounter_id'])
    base = f'/v1/encounters/{eid}'
    tx = timing.measure('normalization', lambda: require(client.get(base+'/workspace', headers=headers), 200)['transcript'])
    tx = timing.measure('extraction', lambda: require(client.patch(base+'/transcripts/'+tx['id'], headers={**headers, 'If-Match': '"'+tx['sha256']+'"'}, json={
        'segments': [{'segment_id': s['segment_id'], 'role': s['role'], 'text': s['text']} for s in tx['segments']],
        'english_confirmed': True, 'source_completeness_reviewed': True,
        'source_review_reason': 'Programmatic synthetic software check only; no human clinical attestation.',
        'correction_reason': 'Programmatic developer-authored fixture review, not independent adjudication.'}), 201))
    facts = require(client.get(base+'/facts', headers=headers), 200)['facts']
    for fact in facts:
        fact.update(reviewed=True, critical_reviewed=True, subject='patient', temporality='current')
    mutated = deepcopy(facts)
    dose = next(f for f in mutated if '0.5 mg' in f['text'])
    dose['text'] = dose['text'].replace('0.5 mg', '5 mg')
    bad = timing.measure('drafting', lambda: require(client.post(base+'/drafts', headers=headers, json={'transcript_version_id': tx['id'], 'facts': mutated}), 201))
    if bad['verification']['gate'] == 'ready':
        raise ValueError('unsafe_synthetic_dose_mutation_admitted')
    def approval(note):
        return client.post(base+'/approvals', headers=headers, json={'note_version_id': note['id'],
            'expected_note_sha256': note['sha256'], 'verification_report_id': note['verification_report_id'],
            'patient_identifiers_reconfirmed': True})
    require(approval(bad['note']), 409)
    good = timing.measure('verification', lambda: require(client.patch(base+'/notes/'+bad['note']['id'], headers={**headers, 'If-Match': '"'+bad['note']['sha256']+'"'},
        json={'transcript_version_id': tx['id'], 'facts': facts}), 201))
    approved = timing.measure('clinician_review', lambda: require(approval(good['note']), 201))
    exports = []
    for format in ('markdown', 'text', 'json', 'fhir'):
        receipt = timing.measure('export', lambda format=format: require(client.post(base+'/exports', headers=headers, json={'approval_id': approved['id'], 'format': format}), 201))
        body = client.get(receipt['download_url'], headers=headers)
        import hashlib
        if body.status_code != 200 or hashlib.sha256(body.content).hexdigest() != receipt['sha256']:
            raise ValueError('offline_export_integrity_failure')
        exports.append({'format': format, 'sha256': receipt['sha256']})
    viewer = {'Authorization': 'Bearer '+config['viewer_key']}
    require(client.get(base+'/workspace', headers=viewer), 200)
    require(client.post('/v1/demo', headers=viewer), 403)
    return {'schema_version': 'offline_walkthrough_v1', 'encounter_id': eid,
            'synthetic_dose_error_blocked': True, 'unsafe_approval_http_status': 409,
            'corrected_version_approved': True, 'exports': exports, 'viewer_write_denied': True,
            'provider_calls': 0, 'independent_clinical_gold': False, 'real_patient_release_authorized': False,
            'stage_latency': timing.report(),
            'limitations': 'Programmatic scripted review flags exercise software only. Silent transport audio is not clinical speech or ASR accuracy evidence.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8010)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--root', default=None)
    args = parser.parse_args()
    if os.getenv('MED_TRANSCRIPT_ENV') == 'production':
        raise ValueError('Standalone synthetic simulator is forbidden in production')
    os.environ.update(MED_TRANSCRIPT_OFFLINE='1', MED_TRANSCRIPT_PROFILE='no_external_dependency',
                      MED_TRANSCRIPT_AUTH_MODE='local', MED_TRANSCRIPT_DRAFTING_MODE='deterministic')
    root = args.root or f'data/offline-demo-{uuid4()}'
    app, config = prepare(root)
    result = walkthrough(app, config)
    if args.self_test:
        print(json.dumps(result))
    else:
        print('Offline synthetic demo: http://127.0.0.1:'+str(args.port))
        print('Access credentials: '+str(Path(root)/'access.json')+' (values are not logged).')
        import uvicorn
        uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)
