"""Failure-inclusive paired study summaries; no simulated clinician observations."""
import argparse
import json
import math
from pathlib import Path
from statistics import median


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def summarize(document):
    roster = document['planned_pairs']
    if not roster or any(not isinstance(x, str) or not x.strip() for x in roster) or len(set(roster)) != len(roster):
        raise ValueError('Frozen unique planned pair roster required')
    if not isinstance(document.get('protocol_sha256'), str) or len(document['protocol_sha256']) != 64:
        raise ValueError('Frozen protocol SHA256 required')
    try:
        int(document['protocol_sha256'], 16)
    except ValueError:
        raise ValueError('Invalid protocol SHA256') from None
    rows = {}
    for row in document['observations']:
        pair, mode = row['pair_id'], row['mode']
        if pair not in roster or mode not in ('manual', 'assisted') or (pair, mode) in rows:
            raise ValueError('Unknown/duplicate pair or condition')
        if row.get('status') not in ('complete', 'failed'):
            raise ValueError('Explicit outcome required')
        if row['status'] == 'complete':
            if not number(row.get('wall_seconds')) or not number(row.get('critical_errors')) or type(row['critical_errors']) is not int:
                raise ValueError('Observed duration and integer critical-error count required')
        for field in ('provider_cost', 'hardware_cost'):
            if row.get(field) is not None and not number(row[field]):
                raise ValueError('Cost must be finite, nonnegative or unknown')
        rows[pair, mode] = row
    pairs, differences = [], []
    for pair in roster:
        manual, assisted = rows.get((pair, 'manual')), rows.get((pair, 'assisted'))
        complete = all(r is not None and r['status'] == 'complete' for r in (manual, assisted))
        delta = manual['wall_seconds']-assisted['wall_seconds'] if complete else None
        if complete:
            differences.append(delta)
        pairs.append({'pair_id': pair, 'complete_pair': complete, 'seconds_saved': delta})
    attempted = list(rows.values())
    costs = {field: sum(r[field] for r in attempted) if attempted and all(r.get(field) is not None for r in attempted) else None
             for field in ('provider_cost', 'hardware_cost')}
    return {'schema_version': 'paired_study_v1', 'protocol_sha256': document['protocol_sha256'],
            'planned_pairs': len(roster), 'observed_conditions': len(rows),
            'missing_conditions': 2*len(roster)-len(rows),
            'failed_conditions': sum(r['status'] == 'failed' for r in attempted),
            'complete_pairs': len(differences), 'incomplete_pairs': len(roster)-len(differences),
            'median_seconds_saved_complete_pairs_only': median(differences) if differences else None,
            'critical_errors_complete_conditions': sum(r['critical_errors'] for r in attempted if r['status'] == 'complete'),
            'cost_totals': costs, 'pairs': pairs,
            'limitations': ['Complete-pair timing is subject to missingness bias; failures remain in counts.',
                           'Wall time includes inactivity. No active-time or causal productivity claim.',
                           'Identity, qualification, randomization and correctness require independent audit.'],
            'clinical_acceptance': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    result = summarize(json.loads(Path(args.input).read_text(encoding='utf-8')))
    with Path(args.out).open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2, allow_nan=False)


if __name__ == '__main__':
    main()
