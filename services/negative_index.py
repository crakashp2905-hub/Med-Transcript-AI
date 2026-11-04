"""Append-only snapshot of preserved negative experiments; never repairs their bytes."""
import argparse
import json
from pathlib import Path
from services.engineering_status import sha256


def reasons(value, location='$'):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            here = location+'.'+key
            if (key == 'complete' and item is False) or (key in ('failed', 'timed_out') and item is True):
                found.append(here)
            elif key in ('failed_cases', 'failed_samples', 'failure_count') and isinstance(item, int) and item > 0:
                found.append(here)
            elif key in ('initialization_failure', 'error_type') and item:
                found.append(here)
            elif key == 'status' and item in ('failed', 'runtime_failed', 'resource_timeout', 'interrupted', 'incomplete'):
                found.append(here)
            found.extend(reasons(item, here))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            found.extend(reasons(item, f'{location}[{i}]'))
    return found


def build(baseline, root='.'):
    root = Path(root).resolve()
    entries = []
    for name, expected in baseline['benchmark_sha256'].items():
        path = (root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or sha256(path) != expected:
            raise ValueError('negative_evidence_missing_or_changed')
        if path.suffix != '.json':
            continue
        data = json.loads(path.read_bytes())
        signals = reasons(data)
        if signals:
            entries.append({'path': name, 'sha256': expected, 'signals': signals})
    return {'schema_version': 'negative_experiments_index_v1', 'source_commit': baseline['source_commit'],
            'inventory_scope': 'All JSON reports in the pre-change hashed baseline; absence from this snapshot is not proof that no other failure exists.',
            'entries': entries, 'original_reports_modified': False, 'independent_clinical_gold': False,
            'real_patient_release_authorized': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    report = build(json.loads(Path('evaluation/reports/engineering-baseline.json').read_text(encoding='utf-8')))
    with Path(args.out).open('x', encoding='utf-8') as target:
        json.dump(report, target, indent=2)
