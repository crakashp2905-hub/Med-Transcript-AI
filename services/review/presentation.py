"""Conservative integration export: preserve approved wording, never infer codes."""
import base64
import json
import hashlib
import re
from pathlib import Path


def campaign_evidence(root):
    """Prefer published final ranking; retain every incomplete experiment."""
    root = Path(root)
    reports = {}
    sources = {}
    choices = {
        'ranking': ['detailed-ranking-final-2026-10-29.json', 'detailed-ranking-v2-2026-10-29.json'],
        'drafting': ['detailed-drafting-summary-2026-10-29.json'],
        'execution': ['detailed-campaign-execution-receipt-2026-10-29.json'],
    }
    for key, filenames in choices.items():
        reports[key] = None
        for filename in filenames:
            path = root / filename
            try:
                raw = path.read_bytes()
                value = json.loads(raw)
            except (OSError, ValueError):
                continue
            reports[key] = value
            sources[key] = {'filename': filename, 'sha256': hashlib.sha256(raw).hexdigest()}
            break
    experiments = []
    for path in sorted((root.parent / 'runs/meddistract-detailed-v2').glob('*.json')):
        try:
            raw = path.read_bytes()
            value = json.loads(raw)
        except (OSError, ValueError):
            continue
        if value.get('mode') == 'fixed':
            continue
        complete = value.get('complete') is True
        experiments.append({'candidate': value.get('candidate_id'), 'mode': value.get('mode'),
            'status': 'complete' if complete else 'incomplete',
            'completed_cases': len(value.get('cases', [])),
            'conditions': value.get('conditions') if complete else None,
            'filename': path.name, 'sha256': hashlib.sha256(raw).hexdigest()})
    return {'reports': reports, 'sources': sources, 'experiments': experiments,
            'clinical_validation': False,
            'scope': 'public synthetic development evidence; not independent clinical acceptance',
            'provider_cost': 0, 'hardware_cost': None}


def public_demo_cases():
    root = Path(__file__).resolve().parents[2]
    manifest = root / 'evaluation/datasets/meddistract-detailed-v1/manifest.json'
    if not manifest.is_file():
        return []
    body = json.loads(manifest.read_text(encoding='utf-8'))
    return [{**c, 'attribution': body['attribution']} for c in body['cases'] if c['condition'] == 'clean']


def public_demo(case_id):
    case = next((c for c in public_demo_cases() if c['group_id'] == case_id), None)
    if case is None:
        raise ValueError('unknown_public_demo')
    root = Path(__file__).resolve().parents[2] / 'data/datasets/meddistract-detailed-v1'
    source = (root / case['audio']).resolve()
    if source.parent != root.resolve() or hashlib.sha256(source.read_bytes()).hexdigest() != case['audio_sha256']:
        raise ValueError('public_demo_integrity_failure')
    return source, {'segments': [{'start_ms': t['start_ms'], 'end_ms': t['end_ms'],
        'text': re.sub(r'<[^>]*>', '', t['reference']),
        'role': 'clinician' if t['role'] == 'doctor' else t['role']} for t in case['reference_turns']],
        'attribution': case['attribution'], 'case_id': case_id}


def fhir_document(note, approval):
    # R4 DocumentReference with an inline JSON attachment. Not a transaction or
    # a coded MedicationRequest/AllergyIntolerance, and not an EHR write.
    payload = json.dumps({'note': note, 'approval': approval}, ensure_ascii=False).encode('utf-8')
    return json.dumps({
        'resourceType': 'DocumentReference', 'id': note['id'],
        'identifier': [{'system': 'urn:med-transcript:note-sha256', 'value': approval['note_sha256']}],
        'status': 'current', 'docStatus': 'final', 'date': approval['approved_at'],
        'description': 'Synthetic approved note; integration prototype. Validate against receiving-system profiles before import.',
        'context': {'encounter': [{'identifier': {'system': 'urn:med-transcript:encounter', 'value': note['encounter_id']}}]},
        'content': [{'attachment': {'contentType': 'application/json', 'title': 'Approved evidence-linked note',
                                    'data': base64.b64encode(payload).decode('ascii')}}],
    }, ensure_ascii=False, indent=2)
