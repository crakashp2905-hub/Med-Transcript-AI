import pytest

from services.throughput_measurement import record


def test_throughput_record_captures_warm_cold_hardware_and_queue_fields():
    result = record(mode='cold', cpu_threads=4, ram_gb=16, runtime_seconds=12.5, queue_wait_seconds=0.4, model_digest='local')
    assert result['mode'] == 'cold' and result['cpu_threads'] == 4 and result['ram_gb'] == 16
    assert result['queue_wait_seconds'] == 0.4 and result['clinical_capacity_claim'] is False


def test_throughput_record_rejects_invalid_mode():
    with pytest.raises(ValueError, match='invalid_run_mode'):
        record(mode='unknown', cpu_threads=4, ram_gb=16, runtime_seconds=1, queue_wait_seconds=0)
