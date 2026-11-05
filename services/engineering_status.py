"""Evidence-backed task counts. Missing/changed evidence cannot count as verified."""
import argparse
import hashlib
import json
from pathlib import Path

STATUSES = {'implemented', 'verified', 'failed', 'blocked_external_evidence', 'blocked_missing_local_artifact', 'not_started'}


def verify_ci_receipt(receipt, expected_commit):
    required = {'frontend', 'postgres', 'container', 'test (dev,security)', 'test (dev,asr,security)'}
    if receipt['source_commit'] != expected_commit or receipt['status'] != 'completed' or receipt['conclusion'] != 'success':
        raise ValueError('hosted_ci_not_verified')
    if {j['name'] for j in receipt['jobs']} != required or any(j['status'] != 'completed' or j['conclusion'] != 'success' for j in receipt['jobs']):
        raise ValueError('hosted_ci_missing_or_failed_jobs')
    return {'jobs_verified': len(required), 'source_commit': expected_commit, 'real_patient_release_authorized': False}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def evidence_sha256(path, mode='bytes', relative_name=None):
    path=Path(path)
    if mode=='bytes':return sha256(path)
    if mode!='normalized_source_text':raise ValueError('unknown_evidence_hash_mode')
    namespace=Path(relative_name) if relative_name is not None else path
    parts=namespace.parts
    if ('evaluation' in parts or any(a=='docs' and b=='plans' for a,b in zip(parts,parts[1:]))
        or path.suffix.lower() not in {'.py','.ts','.tsx','.md','.ps1','.yml','.yaml','.cmd'}):
        raise ValueError('artifact_bytes_cannot_be_normalized')
    return hashlib.sha256(path.read_text(encoding='utf-8').encode('utf-8')).hexdigest()


def evidence_record(name, root='.'):
    path=Path(name)
    try:namespace=path.resolve().relative_to(Path(root).resolve())
    except ValueError:namespace=path
    mode='normalized_source_text'
    try:digest=evidence_sha256(path,mode,namespace)
    except ValueError:
        mode='bytes';digest=sha256(path)
    return {'path':namespace.as_posix(),'sha256':digest,'hash_mode':mode}


def validate(document, root='.'):
    root = Path(root).resolve()
    ids = [t['id'] for t in document['tasks']]
    if len(ids) != document['total'] or len(set(ids)) != len(ids):
        raise ValueError('task_count_or_identity_mismatch')
    for task in document['tasks']:
        if task['status'] not in STATUSES:
            raise ValueError('unknown_task_status')
        if task['status'] != 'verified':
            continue
        if not task['evidence'] or not task['tests'] or not task.get('limitations'):
            raise ValueError('verified_task_missing_evidence')
        for evidence in task['evidence']:
            path = (root / evidence['path']).resolve()
            if not path.is_relative_to(root) or not path.is_file() or evidence_sha256(path,evidence.get('hash_mode','bytes'),evidence['path']) != evidence['sha256']:
                raise ValueError('verified_evidence_missing_or_changed')
    complete = sum(t['status'] == 'verified' for t in document['tasks'])
    return {'verified': complete, 'total': len(ids), 'percent': round(100*complete/len(ids), 2),
            'statuses': {s: sum(t['status'] == s for t in document['tasks']) for s in sorted(STATUSES)},
            'real_patient_release_authorized': False}


def render(document, root='.'):
    result = validate(document, root)
    lines = ['# Engineering scorecard', '', f"**{result['verified']}/{result['total']} verified ({result['percent']:.2f}%).**", '',
             'Clinical release: `BLOCKED_EXTERNAL_EVIDENCE_REQUIRED`. A missing local model or tool is not a pass.', '',
             '| Task | Status | Evidence | Tests / next action |', '| --- | --- | --- | --- |']
    for task in document['tasks']:
        paths = ', '.join(f"[{e['path']}](../{e['path']})" for e in task['evidence']) or '—'
        detail = '; '.join(task['tests']) if task['tests'] else task['limitations']
        lines.append(f"| {task['id']} — {task['description'].replace('|', '/')} | {task['status']} | {paths} | {detail.replace('|', '/')} |")
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status', default='evaluation/reports/engineering-task-status.json')
    parser.add_argument('--write-scorecard', action='store_true')
    parser.add_argument('--diagnostics', action='store_true')
    args = parser.parse_args()
    document = json.loads(Path(args.status).read_text(encoding='utf-8'))
    if args.write_scorecard:
        Path('docs/engineering-scorecard.md').write_text(render(document), encoding='utf-8')
    result = validate(document)
    if args.diagnostics:
        from services.offline_preflight import inspect
        import os
        summary = Path('data/offline-acceptance-summary.json')
        result.update(offline_mode=os.getenv('MED_TRANSCRIPT_OFFLINE') == '1',
                      capabilities=inspect(),
                      latest_local_acceptance=json.loads(summary.read_text(encoding='utf-8')) if summary.is_file() else 'not_established',
                      clinical_release='BLOCKED_EXTERNAL_EVIDENCE_REQUIRED')
    print(json.dumps(result))
