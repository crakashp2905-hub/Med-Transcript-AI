"""Bounded queue admission policy under overload."""


def admit(*, queued, capacity):
    if queued < 0 or capacity < 0:
        raise ValueError('invalid_queue_size')
    if queued < capacity:
        return {'accepted': True, 'action': 'enqueue'}
    return {'accepted': False, 'action': 'reject', 'reason': 'queue_capacity'}
