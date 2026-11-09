"""Controlled, failure-preserving throughput measurement envelopes."""


def record(*, mode, cpu_threads, ram_gb, runtime_seconds, queue_wait_seconds, status='succeeded', model_digest=None):
    if mode not in ('cold', 'warm'):
        raise ValueError('invalid_run_mode')
    values = (cpu_threads, ram_gb, runtime_seconds, queue_wait_seconds)
    if not isinstance(cpu_threads, int) or cpu_threads < 1 or any(type(v) not in (int, float) or v < 0 for v in values[1:]):
        raise ValueError('invalid_hardware_measurement')
    return {'schema_version': 'throughput_measurement_v1', 'mode': mode, 'cpu_threads': cpu_threads,
            'ram_gb': ram_gb, 'runtime_seconds': runtime_seconds, 'queue_wait_seconds': queue_wait_seconds,
            'status': status, 'model_digest': model_digest, 'clinical_capacity_claim': False}
