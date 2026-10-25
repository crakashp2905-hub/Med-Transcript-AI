"""Reproducible development evaluation; never manufactures clinical gold labels."""
import argparse
import hashlib
import json
from pathlib import Path

from services.clinical_metrics import evaluate
from services.review.clinical import check_claim


def adversarial(path):
    raw = Path(path).read_bytes()
    fixture = json.loads(raw)
    rows = []
    counts = dict(true_positive=0, false_positive=0, true_negative=0, false_negative=0)
    for case in fixture['cases']:
        findings = check_claim(case['source'], case['claim'])
        unsafe, expected = bool(findings), case['expected_unsafe']
        key = ('true_' if unsafe == expected else 'false_') + ('positive' if unsafe else 'negative')
        counts[key] += 1
        rows.append({'id': case['id'], 'category': case['category'], 'expected_unsafe': expected,
                     'detected_unsafe': unsafe, 'findings': [x['code'] for x in findings]})
    return {'fixture_sha256': hashlib.sha256(raw).hexdigest(),
            'scope': fixture['annotation_status'], 'validator': 'independent_clinical_rules_v2',
            'limitation': 'Small synthetic developer fixture; not an estimate of clinical sensitivity or specificity.',
            'confusion_matrix': counts, 'cases': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adversarial')
    parser.add_argument('--annotated', help='JSON cases: reference, hypothesis, expected and observed independent concept annotations, failed')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if bool(args.adversarial) == bool(args.annotated):
        parser.error('Choose exactly one evaluation source')
    if args.adversarial:
        report = adversarial(args.adversarial)
    else:
        raw = Path(args.annotated).read_bytes()
        cases = json.loads(raw)['cases']
        report = {'source_sha256': hashlib.sha256(raw).hexdigest(),
                  'cases': [{'id': c['id'], **evaluate(c['reference'], c['hypothesis'],
                    c['expected'], c['observed'], c.get('failed', False))} for c in cases],
                  'limitation': 'Annotation quality requires independent clinical adjudication.'}
    Path(args.output).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
