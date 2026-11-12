"""Transparent local-resource accounting with no invented market prices."""

import math


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"invalid_{name}")
    return float(value)


def successful_consultation_cost(stages, *, cpu_watts, electricity_usd_per_kwh):
    """Return measured usage and electricity cost for successful stages only.

    Memory and disk are retained as measured resource quantities. Their market
    costs remain ``None`` unless the operator supplies an audited price model.
    Failed/unavailable stages make the consultation cost unknown.
    """
    watts = _number(cpu_watts, "cpu_watts")
    rate = _number(electricity_usd_per_kwh, "electricity_usd_per_kwh")
    if not isinstance(stages, (list, tuple)) or not stages:
        raise ValueError("stages_required")
    cpu_seconds = memory_gb_seconds = disk_gb_seconds = 0.0
    for stage in stages:
        if not isinstance(stage, dict) or stage.get("status") != "succeeded":
            return {
                "status": "unknown",
                "reason": "incomplete_consultation",
                "electricity_cost_usd": None,
                "cpu_seconds": None,
                "memory_gb_seconds": None,
                "disk_gb_seconds": None,
                "hardware_market_cost_usd": None,
                "real_patient_release_authorized": False,
            }
        cpu_seconds += _number(stage.get("cpu_seconds"), "cpu_seconds")
        memory_gb_seconds += _number(
            stage.get("memory_gb_seconds", 0), "memory_gb_seconds"
        )
        disk_gb_seconds += _number(stage.get("disk_gb_seconds", 0), "disk_gb_seconds")
    energy_kwh = cpu_seconds * watts / 3_600_000
    return {
        "status": "measured",
        "cpu_seconds": cpu_seconds,
        "memory_gb_seconds": memory_gb_seconds,
        "disk_gb_seconds": disk_gb_seconds,
        "energy_kwh": energy_kwh,
        "electricity_usd_per_kwh": rate,
        "electricity_cost_usd": energy_kwh * rate,
        "hardware_market_cost_usd": None,
        "real_patient_release_authorized": False,
    }
