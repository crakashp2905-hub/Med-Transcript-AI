import pytest

from services.throughput_measurement import record


def test_throughput_record_captures_warm_cold_hardware_and_queue_fields():
    result = record(
        mode="cold",
        cpu_threads=4,
        ram_gb=16,
        runtime_seconds=12.5,
        queue_wait_seconds=0.4,
        model_digest="local",
        completed_units=8,
    )
    assert (
        result["mode"] == "cold"
        and result["cpu_threads"] == 4
        and result["ram_gb"] == 16
    )
    assert result["throughput_units_per_second"] == 8 / 12.5
    assert (
        result["queue_wait_seconds"] == 0.4
        and result["clinical_capacity_claim"] is False
    )


def test_throughput_record_rejects_invalid_mode():
    with pytest.raises(ValueError, match="invalid_run_mode"):
        record(
            mode="unknown",
            cpu_threads=4,
            ram_gb=16,
            runtime_seconds=1,
            queue_wait_seconds=0,
        )


def test_throughput_record_rejects_invalid_completed_unit_count():
    with pytest.raises(ValueError, match="invalid_hardware_measurement"):
        record(
            mode="warm",
            cpu_threads=2,
            ram_gb=8,
            runtime_seconds=1,
            queue_wait_seconds=0,
            completed_units=-1,
        )
