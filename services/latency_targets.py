"""Explicit development latency targets with failure-preserving evaluation."""
TARGETS_SECONDS = {
    'single_cpu_16gb': {'recording': 1.0, 'transfer': 5.0, 'normalization': 30.0, 'asr': 300.0,
                        'diarization': 180.0, 'extraction': 30.0, 'drafting': 30.0,
                        'verification': 30.0, 'clinician_review': 600.0, 'export': 10.0},
    'developer_laptop': {'recording': 1.0, 'transfer': 3.0, 'normalization': 20.0, 'asr': 180.0,
                         'diarization': 120.0, 'extraction': 20.0, 'drafting': 20.0,
                         'verification': 20.0, 'clinician_review': 600.0, 'export': 5.0},
}


def evaluate(stage_report, device_class):
    if device_class not in TARGETS_SECONDS:
        raise ValueError('unknown_latency_device_class')
    stages = stage_report.get('stages', {}) if isinstance(stage_report, dict) else {}
    result = {}
    for name, target in TARGETS_SECONDS[device_class].items():
        value = stages.get(name, {})
        status = value.get('status', 'not_started')
        seconds = value.get('wall_seconds')
        if status != 'succeeded':
            result[name] = {'status': status, 'target_seconds': target, 'met': None,
                            'reported_seconds': seconds, 'error_code': value.get('error_code')}
        else:
            if type(seconds) not in (int, float) or seconds < 0:
                raise ValueError('invalid_latency_seconds')
            result[name] = {'status': status, 'target_seconds': target, 'met': seconds <= target,
                            'reported_seconds': seconds, 'error_code': None}
    return {'schema_version': 'latency_targets_v1', 'device_class': device_class,
            'stages': result, 'complete': all(v['met'] is True for v in result.values()),
            'limitations': 'Targets are development hypotheses; unavailable or failed stages remain visible and do not count as passes.'}
