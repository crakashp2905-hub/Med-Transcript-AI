"""Deterministic worker crash and stale-lease recovery transitions."""


def recover(*, stage, lease_state, checkpoint):
    if lease_state not in {'active', 'stale', 'missing'}:
        raise ValueError('invalid_lease_state')
    if not isinstance(checkpoint, dict):
        raise ValueError('checkpoint_required')
    if lease_state == 'active':
        return {'action': 'resume_checkpoint', 'stage': stage, 'checkpoint': checkpoint, 'publish': False}
    return {'action': 'reacquire_lease', 'stage': stage, 'checkpoint': checkpoint, 'publish': False}
