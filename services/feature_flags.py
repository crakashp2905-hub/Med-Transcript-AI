"""Explicit feature flags preserving frozen baseline behavior."""


def select(*, proposed_enabled=False, baseline='deterministic'):
    if baseline != 'deterministic':
        raise ValueError('baseline_must_be_deterministic')
    return {'baseline': baseline, 'proposed_enabled': bool(proposed_enabled),
            'active_method': 'proposed' if proposed_enabled else baseline}
