import pytest

from services.local_cost import successful_consultation_cost


def test_local_cost_uses_measured_cpu_and_explicit_electricity_assumption():
    value = successful_consultation_cost([
        {'status': 'succeeded', 'cpu_seconds': 3600, 'memory_gb_seconds': 7200, 'disk_gb_seconds': 30},
        {'status': 'succeeded', 'cpu_seconds': 1800, 'memory_gb_seconds': 3600, 'disk_gb_seconds': 10},
    ], cpu_watts=100, electricity_usd_per_kwh=.20)
    assert value['status'] == 'measured'
    assert value['cpu_seconds'] == 5400
    assert value['energy_kwh'] == pytest.approx(.15)
    assert value['electricity_cost_usd'] == pytest.approx(.03)
    assert value['hardware_market_cost_usd'] is None


def test_local_cost_preserves_incomplete_or_invalid_measurements():
    incomplete = successful_consultation_cost([{'status': 'unavailable'}], cpu_watts=100, electricity_usd_per_kwh=.2)
    assert incomplete['status'] == 'unknown' and incomplete['electricity_cost_usd'] is None
    with pytest.raises(ValueError, match='invalid_cpu_seconds'):
        successful_consultation_cost([{'status': 'succeeded', 'cpu_seconds': -1}], cpu_watts=100, electricity_usd_per_kwh=.2)
