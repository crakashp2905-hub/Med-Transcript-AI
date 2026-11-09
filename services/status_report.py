"""Single-command, read-only local readiness report; never runs inference."""
import argparse
import json
import os
import subprocess
from pathlib import Path

from services.engineering_status import evidence_record, validate
from services.offline_preflight import inspect


def build(root='.'):
    root = Path(root).resolve()
    ledger = json.loads((root / 'evaluation/reports/engineering-task-status.json').read_text(encoding='utf-8'))
    counts = validate(ledger, root)
    acceptance_path = root / 'data/offline-acceptance-summary.json'
    acceptance = json.loads(acceptance_path.read_text(encoding='utf-8')) if acceptance_path.is_file() else None
    checks = acceptance.get('checks', {}) if isinstance(acceptance, dict) else {}
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = 'unavailable'
    source_files = ('pyproject.toml', 'constraints-ci.txt', 'services/engineering_status.py',
                    'services/offline_preflight.py', 'services/release_policy.py')
    return {
        'schema_version': 'local_status_v1',
        'git_commit': commit,
        'offline_mode': os.getenv('MED_TRANSCRIPT_OFFLINE') == '1',
        'test_status': {'latest_acceptance': {k: v.get('status') if isinstance(v, dict) else v for k, v in checks.items()},
                        'source': 'saved_acceptance_only', 'inference_executed': False},
        'model_availability': inspect(root)['models'],
        'source_hashes': [evidence_record(name, root) for name in source_files if (root / name).is_file()],
        'engineering': counts,
        'clinical_release': 'BLOCKED_EXTERNAL_EVIDENCE_REQUIRED',
        'real_patient_release_authorized': False,
        'limitations': 'Read-only diagnostics; a saved test receipt is not a fresh test run and model presence is not model eligibility.'
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    print(json.dumps(build(args.root), indent=2))
