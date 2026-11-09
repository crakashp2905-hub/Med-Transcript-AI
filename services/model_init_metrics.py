"""Cold/warm model initialization measurement envelope."""


def record(*, cold_seconds, warm_seconds, cold_bytes, warm_bytes):
    values = (cold_seconds, warm_seconds, cold_bytes, warm_bytes)
    if any(value < 0 for value in values):
        raise ValueError('metrics_must_be_nonnegative')
    return {'cold_seconds': cold_seconds, 'warm_seconds': warm_seconds,
            'cold_bytes': cold_bytes, 'warm_bytes': warm_bytes,
            'warm_speedup': None if warm_seconds == 0 else cold_seconds / warm_seconds,
            'cache_effect': cold_bytes != warm_bytes}
