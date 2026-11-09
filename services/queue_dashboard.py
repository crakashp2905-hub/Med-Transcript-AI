"""Serializable durable-queue dashboard snapshots."""


def snapshot(*, stage, attempts, lease_owner, timeout_seconds, consent_state):
    if attempts < 0 or timeout_seconds < 0:
        raise ValueError('invalid_queue_counters')
    if consent_state not in {'active', 'revoked', 'unknown'}:
        raise ValueError('invalid_consent_state')
    return {'stage': stage, 'attempts': attempts, 'lease_owner': lease_owner,
            'timeout_seconds': timeout_seconds, 'consent_state': consent_state,
            'revoked': consent_state == 'revoked'}
