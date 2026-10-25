"""Offline independent-review intake. Identity/qualification attestations need human audit."""
import argparse
import hashlib
import json
from pathlib import Path
from collections import Counter

from services.clinical_metrics import evaluate


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def packet(manifest):
    cases = [{k: c[k] for k in ('group_id', 'audio', 'audio_sha256', 'duration_ms',
                                'reference_turns')} for c in manifest['cases']]
    if not cases or len({c['group_id'] for c in cases}) != len(cases):
        raise ValueError('Unique nonempty source cases required')
    source = {'dataset_id': manifest['dataset_id'], 'cases': cases}
    return {'schema_version': 'independent_review_v1', 'source': source,
            'source_sha256': digest(source), 'reviewer_id': '',
            'qualified_reviewer_attestation': False, 'audio_reviewed_attestation': False,
            'independent_review_attestation': False,
            'annotations': [{'id': c['group_id'], 'concepts': [], 'complete': False}
                            for c in cases]}


def validate(review, source):
    if review['source_sha256'] != digest(source) or review['source'] != source:
        raise ValueError('Source changed or wrong review packet')
    if not isinstance(review['reviewer_id'], str) or not review['reviewer_id'].strip():
        raise ValueError('Reviewer identity required')
    for field in ('qualified_reviewer_attestation', 'audio_reviewed_attestation',
                  'independent_review_attestation'):
        if review.get(field) is not True:
            raise ValueError('Human reviewer attestations required')
    expected = {c['group_id']: c for c in source['cases']}
    rows = review['annotations']
    if len(rows) != len(expected) or {r['id'] for r in rows} != set(expected):
        raise ValueError('Every source case required exactly once')
    result = {}
    for row in rows:
        if row.get('complete') is not True:
            raise ValueError('Incomplete case review')
        concepts = row['concepts']
        if not isinstance(concepts, list) or len(concepts) > 10000:
            raise ValueError('Invalid concept list')
        ids = set()
        for concept in concepts:
            # The existing frozen exact-concept scorer validates required clinical slots.
            evaluate('', '', [concept], [])
            enums={'category':{'medication','dose','allergy','negation','symptom','measurement','assessment','plan','other'},
                   'subject':{'patient','family','caregiver','other','unknown'},
                   'assertion':{'affirmed','negated','uncertain','not_stated'},
                   'temporality':{'current','historical','planned','unknown'}}
            if any(concept[field] not in options for field,options in enums.items()):
                raise ValueError('Clinical vocabulary must match gold-concept-schema-v1')
            annotation_id = concept.get('annotation_id')
            if not isinstance(annotation_id, str) or not annotation_id or annotation_id in ids:
                raise ValueError('Unique annotation IDs required')
            ids.add(annotation_id)
            ev = concept.get('evidence', {})
            index, start, end = ev.get('turn_index'), ev.get('start'), ev.get('end')
            if any(type(n) is not int for n in (index, start, end)):
                raise ValueError('Integer evidence coordinates required')
            turns = expected[row['id']]['reference_turns']
            if not 0 <= index < len(turns):
                raise ValueError('Evidence turn out of range')
            text = turns[index]['reference']
            if not 0 <= start < end <= len(text) or ev.get('quote') != text[start:end]:
                raise ValueError('Evidence must exactly match frozen source')
            if any(isinstance(v, (dict, list)) for k, v in concept.items() if k != 'evidence'):
                raise ValueError('Clinical slots must be flat scalar values')
        result[row['id']] = concepts
    return result


def key(concept):
    return json.dumps({k: v for k, v in concept.items() if k not in ('evidence', 'annotation_id')},
                      sort_keys=True)


def compare(first, second):
    source = first['source']
    a, b = validate(first, source), validate(second, source)
    if first['reviewer_id'].strip().casefold() == second['reviewer_id'].strip().casefold():
        raise ValueError('Two distinct independent reviewers required')
    rows = []
    for case in source['cases']:
        cid = case['group_id']
        left, right = Counter(map(key, a[cid])), Counter(map(key, b[cid]))
        rows.append({'id': cid, 'matched': sum((left & right).values()),
                     'first_only': list((left-right).elements()),
                     'second_only': list((right-left).elements()),
                     'agreement': left == right})
    return {'schema_version': 'independent_comparison_v1', 'source_sha256': digest(source),
            'review_sha256': [digest(first), digest(second)],
            'reviewer_ids': [first['reviewer_id'], second['reviewer_id']], 'cases': rows,
            'adjudication_required': any(not r['agreement'] for r in rows),
            'clinical_gold': False,
            'qualification_status': 'self_attested_requires_external_credential_check'}


def adjudicate(first, second, final):
    comparison = compare(first, second)
    concepts = validate(final, first['source'])
    identities = {r['reviewer_id'].strip().casefold() for r in (first, second, final)}
    if len(identities) != 3:
        raise ValueError('A third distinct adjudicator required')
    if final.get('review_sha256') != comparison['review_sha256']:
        raise ValueError('Adjudication must bind both exact independent reviews')
    decisions = final.get('decisions', {})
    required = {r['id'] for r in comparison['cases'] if not r['agreement']}
    if not isinstance(decisions, dict) or any(
        not isinstance(decisions.get(cid), str) or not decisions[cid].strip() for cid in required
    ):
        raise ValueError('Explicit human resolution for every disagreement required')
    return {'schema_version': 'adjudicated_candidate_v1',
            'source_sha256': comparison['source_sha256'],
            'review_sha256': comparison['review_sha256'], 'adjudication_sha256': digest(final),
            'reviewer_ids': comparison['reviewer_ids'], 'adjudicator_id': final['reviewer_id'],
            'cases': [{'id': cid, 'expected': rows} for cid, rows in concepts.items()],
            'clinical_gold_status': 'human_submitted_pending_external_credential_and_protocol_audit',
            'clinical_release_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('packet')
    build.add_argument('--manifest', required=True)
    build.add_argument('--lock', required=True)
    check = sub.add_parser('compare')
    check.add_argument('--first', required=True)
    check.add_argument('--second', required=True)
    finish = sub.add_parser('adjudicate')
    finish.add_argument('--first', required=True)
    finish.add_argument('--second', required=True)
    finish.add_argument('--final', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    if args.command == 'packet':
        if hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest() != read(args.lock)['manifest_sha256']:
            raise ValueError('Frozen manifest integrity failure')
        result = packet(read(args.manifest))
    elif args.command == 'compare':
        result = compare(read(args.first), read(args.second))
    else:
        result = adjudicate(read(args.first), read(args.second), read(args.final))
    # Refuse accidental replacement of an independent review or previous evidence.
    with Path(args.out).open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
