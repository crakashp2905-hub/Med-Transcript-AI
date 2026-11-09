"""Synthetic long-duration multi-channel transport stress envelope."""


def record(*, duration_minutes, channels, transport_seconds, wer):
    if duration_minutes not in {20, 30} or channels != 8 or transport_seconds < 0 or not 0 <= wer <= 1:
        raise ValueError('invalid_stress_scenario')
    return {'duration_minutes': duration_minutes, 'channels': channels,
            'transport_seconds': transport_seconds, 'normalized_wer': wer,
            'transport_accuracy_separate': True}
