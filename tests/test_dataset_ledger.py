import json
from pathlib import Path

from services.dataset_ledger import build, metric_hashes


def test_dataset_ledger_keeps_cohorts_separate_and_paired_dependence_explicit():
    ledger = build('.')
    ids = {row['dataset_id'] for row in ledger['datasets']}
    assert len(ids) >= 3 and ledger['paired_clean_distracted_independence'] == 'not_claimed'
    assert all(row['manifest_sha256'] for row in ledger['datasets'])
    assert any(row['protocol_sha256'] for row in ledger['datasets'])
    assert any(row['license_id'] and row['split_role'] for row in ledger['datasets'])


def test_metric_hashes_change_when_reference_or_hypothesis_changes():
    report = json.loads(Path('evaluation/runs/primock57-expanded-v1/omi-med-stt-v1.json').read_text(encoding='utf-8'))
    original = metric_hashes(report)
    changed = dict(report); changed['samples'] = [dict(report['samples'][0], hypothesis='changed')] + report['samples'][1:]
    assert original['reference_sha256'] == metric_hashes(changed)['reference_sha256']
    assert original['hypothesis_sha256'] != metric_hashes(changed)['hypothesis_sha256']
