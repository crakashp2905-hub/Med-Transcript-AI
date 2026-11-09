import pytest

from services.latency_targets import evaluate


def test_latency_targets_keep_unavailable_stages_unmet_without_inventing_values():
    report = evaluate({'stages': {'transfer': {'status': 'succeeded', 'wall_seconds': 1},
                                  'asr': {'status': 'unavailable', 'error_code': 'model_missing'}}}, 'single_cpu_16gb')
    assert report['stages']['transfer']['met'] is True
    assert report['stages']['asr']['met'] is None
    assert report['complete'] is False


def test_latency_targets_reject_unknown_device_or_bad_success_measurement():
    with pytest.raises(ValueError, match='unknown_latency_device_class'):
        evaluate({'stages': {}}, 'gpu_cluster')
    with pytest.raises(ValueError, match='invalid_latency_seconds'):
        evaluate({'stages': {'recording': {'status': 'succeeded', 'wall_seconds': -1}}}, 'developer_laptop')
