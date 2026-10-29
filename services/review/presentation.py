"""Conservative integration export: preserve approved wording, never infer codes."""
import base64
import json
import hashlib
import re
from pathlib import Path


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
