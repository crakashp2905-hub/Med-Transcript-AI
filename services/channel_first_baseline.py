"""Compare channel-first and single-mic duration metrics without role claims."""


def compare(channel_metrics, single_mic_metrics):
    required = ('speech_ms', 'missed_ms', 'false_alarm_ms')
    if not all(all(key in row for key in required) for row in (channel_metrics, single_mic_metrics)):
        raise ValueError('duration_metrics_required')
    return {'channel_first': dict(channel_metrics), 'single_mic': dict(single_mic_metrics),
            'role_accuracy': None, 'clinical_acceptance': False}
