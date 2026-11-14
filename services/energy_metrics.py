"""Separate meter-backed energy from scenario estimates and unknowns."""

import math


POWER_SOURCES = {
    "meter_reading",
    "system_telemetry",
    "documented_assumption",
    "unknown",
}


def summarize_energy(runs):
    if not isinstance(runs, list) or not runs:
        raise ValueError("energy_runs_required")
    seen = set()
    output = []
    measured_total = estimated_total = 0.0
    measured_count = estimated_count = unknown_count = 0
    for row in runs:
        if not isinstance(row, dict):
            raise ValueError("energy_run_invalid")
        run_id, duration = row.get("run_id"), row.get("runtime_seconds")
        source, watts = row.get("power_source"), row.get("average_watts")
        reference = row.get("assumption_or_meter_reference")
        if (
            not isinstance(run_id, str)
            or not run_id
            or run_id in seen
            or not isinstance(duration, (int, float))
            or isinstance(duration, bool)
            or not math.isfinite(duration)
            or duration < 0
            or source not in POWER_SOURCES
        ):
            raise ValueError("energy_run_fields_invalid")
        seen.add(run_id)
        if source == "unknown":
            if watts is not None:
                raise ValueError("unknown_power_cannot_claim_watts")
            energy = None
            evidence_class = "unknown"
            unknown_count += 1
        else:
            if (
                not isinstance(watts, (int, float))
                or isinstance(watts, bool)
                or not math.isfinite(watts)
                or watts <= 0
                or not isinstance(reference, str)
                or not reference.strip()
            ):
                raise ValueError("power_value_and_source_reference_required")
            energy = watts * duration / 3_600_000
            if source == "documented_assumption":
                evidence_class = "scenario_estimate"
                estimated_total += energy
                estimated_count += 1
            else:
                evidence_class = "power_input_observed"
                measured_total += energy
                measured_count += 1
        output.append(
            {
                "run_id": run_id,
                "runtime_seconds": duration,
                "power_source": source,
                "average_watts": watts,
                "energy_kwh": energy,
                "evidence_class": evidence_class,
                "assumption_or_meter_reference": reference,
            }
        )
    return {
        "schema_version": "local_energy_accounting_v1",
        "runs": output,
        "measured_power_input_energy_kwh": measured_total if measured_count else None,
        "scenario_estimated_energy_kwh": estimated_total if estimated_count else None,
        "unknown_energy_run_count": unknown_count,
        "measured_power_input_run_count": measured_count,
        "scenario_estimate_run_count": estimated_count,
        "clinical_or_product_energy_claim": False,
    }
