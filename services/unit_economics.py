"""Transparent per-encounter local-compute cost estimates."""

import math


REQUIRED_INPUTS = (
    "system_watts",
    "runtime_seconds",
    "electricity_price_per_kwh",
    "model_availability_fraction",
    "hardware_capital_cost",
    "amortization_months",
    "scheduled_hours_per_month",
    "encounters_per_active_hour",
)


def estimate(scenario):
    """Return a cost only when every required value and its basis are explicit."""
    if not isinstance(scenario, dict):
        raise ValueError("scenario_must_be_an_object")
    assumptions = scenario.get("inputs")
    currency = scenario.get("currency_unit")
    if (
        not isinstance(assumptions, dict)
        or not isinstance(currency, str)
        or not currency.strip()
    ):
        raise ValueError("scenario_inputs_and_currency_unit_required")

    missing = [
        name
        for name in REQUIRED_INPUTS
        if not isinstance(assumptions.get(name), dict)
        or assumptions[name].get("value") is None
        or assumptions[name].get("basis") not in {"measured", "assumed"}
    ]
    receipt = {
        "schema_version": "local_unit_economics_v1",
        "scenario_id": scenario.get("scenario_id"),
        "currency_unit": currency,
        "inputs": assumptions,
        "missing_measurements": missing,
        "clinical_acceptance": False,
        "clinical_release_authorized": False,
    }
    if missing:
        return {
            **receipt,
            "status": "unavailable",
            "evidence_status": "incomplete_inputs",
            "energy_cost_per_encounter": None,
            "hardware_amortization_per_encounter": None,
            "estimated_cost_per_encounter": None,
        }

    values = {name: assumptions[name]["value"] for name in REQUIRED_INPUTS}
    for name, value in values.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"invalid_input:{name}")
    if any(values[name] < 0 for name in REQUIRED_INPUTS):
        raise ValueError("cost_inputs_must_not_be_negative")
    if values["system_watts"] <= 0 or values["runtime_seconds"] <= 0:
        raise ValueError("system_power_and_runtime_must_be_positive")
    if values["amortization_months"] <= 0 or values["scheduled_hours_per_month"] <= 0:
        raise ValueError("amortization_period_and_schedule_must_be_positive")
    if values["encounters_per_active_hour"] <= 0:
        raise ValueError("encounter_capacity_must_be_positive")
    if not 0 < values["model_availability_fraction"] <= 1:
        raise ValueError("model_availability_must_be_fraction")

    energy = (
        values["system_watts"]
        * values["runtime_seconds"]
        / 3_600_000
        * values["electricity_price_per_kwh"]
    )
    effective_encounters = (
        values["amortization_months"]
        * values["scheduled_hours_per_month"]
        * values["model_availability_fraction"]
        * values["encounters_per_active_hour"]
    )
    hardware = values["hardware_capital_cost"] / effective_encounters
    bases = {assumptions[name]["basis"] for name in REQUIRED_INPUTS}
    evidence_status = (
        "measured_inputs_only"
        if bases == {"measured"}
        else "assumption_only"
        if bases == {"assumed"}
        else "mixed_measured_and_assumed"
    )
    return {
        **receipt,
        "status": "estimated",
        "evidence_status": evidence_status,
        "effective_encounters_over_amortization_period": effective_encounters,
        "energy_cost_per_encounter": energy,
        "hardware_amortization_per_encounter": hardware,
        "estimated_cost_per_encounter": energy + hardware,
        "formula": {
            "energy": "system_watts * runtime_seconds / 3_600_000 * electricity_price_per_kwh",
            "hardware": "hardware_capital_cost / (amortization_months * scheduled_hours_per_month * model_availability_fraction * encounters_per_active_hour)",
        },
    }
