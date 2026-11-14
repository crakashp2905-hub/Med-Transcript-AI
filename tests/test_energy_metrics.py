import pytest

from services.energy_metrics import summarize_energy


def test_energy_report_separates_meter_assumption_and_unknown():
    report = summarize_energy(
        [
            {
                "run_id": "metered",
                "runtime_seconds": 3600,
                "power_source": "meter_reading",
                "average_watts": 100,
                "assumption_or_meter_reference": "plug-meter-01",
            },
            {
                "run_id": "scenario",
                "runtime_seconds": 1800,
                "power_source": "documented_assumption",
                "average_watts": 80,
                "assumption_or_meter_reference": "datasheet:example",
            },
            {
                "run_id": "unknown",
                "runtime_seconds": 60,
                "power_source": "unknown",
                "average_watts": None,
                "assumption_or_meter_reference": None,
            },
        ]
    )
    assert report["measured_power_input_energy_kwh"] == pytest.approx(0.1)
    assert report["scenario_estimated_energy_kwh"] == pytest.approx(0.04)
    assert report["unknown_energy_run_count"] == 1


def test_energy_report_does_not_accept_unreferenced_power_or_duplicate_run_ids():
    with pytest.raises(ValueError, match="source_reference_required"):
        summarize_energy(
            [
                {
                    "run_id": "a",
                    "runtime_seconds": 10,
                    "power_source": "system_telemetry",
                    "average_watts": 20,
                }
            ]
        )
    base = {
        "run_id": "a",
        "runtime_seconds": 1,
        "power_source": "unknown",
        "average_watts": None,
    }
    with pytest.raises(ValueError, match="fields_invalid"):
        summarize_energy([base, base])
