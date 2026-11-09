"""Machine-checkable evaluation policy for evidence-linked clinical drafts."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ClaimSignature:
    subject: str | None
    predicate: str
    object: str | None
    polarity: Literal['affirmed', 'negated', 'uncertain']
    evidence_ids: tuple[str, ...]


def score_findings(findings, *, weights=None):
    """Return a diagnostic vector and gate; critical contradictions dominate scores."""
    weights = weights or {'critical_contradiction': 1000, 'omission': 10, 'false_block': 1}
    vector = {'critical_contradictions': 0, 'omissions': 0, 'false_blocks': 0, 'unresolved': 0}
    for finding in findings:
        kind = finding.get('kind')
        if kind == 'critical_contradiction': vector['critical_contradictions'] += 1
        elif kind == 'omission': vector['omissions'] += 1
        elif kind == 'false_block': vector['false_blocks'] += 1
        elif kind == 'unresolved': vector['unresolved'] += 1
        else: raise ValueError('unknown_evaluation_finding')
    scalar = (vector['critical_contradictions'] * weights['critical_contradiction'] +
              vector['omissions'] * weights['omission'] + vector['false_blocks'] * weights['false_block'])
    return {'vector': vector, 'scalar_cost': scalar,
            'abstain': bool(vector['critical_contradictions'] or vector['unresolved']),
            'approval_gate': 'blocked' if vector['critical_contradictions'] or vector['omissions'] or vector['unresolved'] else 'review_required',
            'real_patient_release_authorized': False}
