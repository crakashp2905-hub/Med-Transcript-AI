"""Seeded assumption-only workload and local-compute cost sensitivity runs."""

import argparse
import json
import math
import random
from pathlib import Path


INPUTS = {
    "runtime_seconds": (0.1, 3600),
    "system_watts": (1, 10000),
    "electricity_price_per_kwh": (0, 10000),
    "hardware_capital_cost": (0, 1e12),
    "amortization_months": (1, 600),
    "scheduled_hours_per_month": (1, 744),
    "availability_fraction": (0.001, 1),
    "encounters_per_active_hour": (0.001, 10000),
    "daily_demand_encounters": (0, 1e9),
}


def _triangular(spec, name):
    if not isinstance(spec, dict) or set(spec) != {"low", "mode", "high"}:
        raise ValueError(f"invalid_triangular_assumption:{name}")
    low, mode, high = (spec[key] for key in ("low", "mode", "high"))
    floor, ceiling = INPUTS[name]
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in (low, mode, high)
    ):
        raise ValueError(f"invalid_triangular_assumption:{name}")
    if not floor <= low <= mode <= high <= ceiling:
        raise ValueError(f"invalid_triangular_assumption:{name}")
    return low, mode, high


def _percentiles(values):
    ordered = sorted(values)

    def at(q):
        index = (len(ordered) - 1) * q
        lower = math.floor(index)
        upper = math.ceil(index)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)

    return {"p05": at(0.05), "p50": at(0.5), "p95": at(0.95)}


def simulate(scenarios, *, iterations=10000, seed=20261114, operating_hours_per_day=8):
    """Simulate demand/capacity/cost; every input is an explicit assumption."""
    if (
        not isinstance(scenarios, list)
        or not scenarios
        or type(iterations) is not int
        or not 1000 <= iterations <= 1_000_000
        or type(seed) is not int
        or isinstance(operating_hours_per_day, bool)
        or not isinstance(operating_hours_per_day, (int, float))
        or not math.isfinite(operating_hours_per_day)
        or not 0 < operating_hours_per_day <= 24
    ):
        raise ValueError("invalid_workload_simulation_configuration")
    rng = random.Random(seed)
    results = []
    for scenario in scenarios:
        if not isinstance(scenario, dict) or not isinstance(
            scenario.get("scenario_id"), str
        ):
            raise ValueError("scenario_id_required")
        distributions = {
            name: _triangular(scenario.get("inputs", {}).get(name), name)
            for name in INPUTS
        }
        metrics = {
            key: []
            for key in (
                "capacity_encounters_per_day",
                "demand_encounters_per_day",
                "completed_encounters_per_day",
                "unserved_demand_encounters_per_day",
                "estimated_compute_cost_per_encounter",
            )
        }
        for _ in range(iterations):
            sample = {
                key: rng.triangular(bounds[0], bounds[2], bounds[1])
                for key, bounds in distributions.items()
            }
            capacity = (
                operating_hours_per_day
                * sample["availability_fraction"]
                * sample["encounters_per_active_hour"]
            )
            demand = sample["daily_demand_encounters"]
            completed = min(capacity, demand)
            effective_encounters = (
                sample["amortization_months"]
                * sample["scheduled_hours_per_month"]
                * sample["availability_fraction"]
                * sample["encounters_per_active_hour"]
            )
            energy_cost = (
                sample["system_watts"]
                * sample["runtime_seconds"]
                / 3_600_000
                * sample["electricity_price_per_kwh"]
            )
            hardware_cost = sample["hardware_capital_cost"] / effective_encounters
            values = (
                capacity,
                demand,
                completed,
                max(0, demand - capacity),
                energy_cost + hardware_cost,
            )
            for key, value in zip(metrics, values, strict=True):
                metrics[key].append(value)
        results.append(
            {
                "scenario_id": scenario["scenario_id"],
                "input_distributions": scenario["inputs"],
                "outputs": {
                    key: _percentiles(values) for key, values in metrics.items()
                },
            }
        )
    return {
        "schema_version": "synthetic_workload_sensitivity_v1",
        "evidence_class": "hypothetical_assumption_only_monte_carlo",
        "iterations_per_scenario": iterations,
        "seed": seed,
        "operating_hours_per_day_assumption": operating_hours_per_day,
        "results": results,
        "measured_inputs": False,
        "clinical_outcomes_inferred": False,
        "product_market_fit_inferred": False,
        "limitations": [
            "All distributions are invented sensitivity assumptions, not observed customer, hardware, or workload data.",
            "Inputs are sampled independently; correlations, queues, outages, staffing, support, taxes, and non-compute costs are not modeled.",
            "Capacity and cost outputs are not clinical performance, staffing recommendations, forecasts, or evidence of product-market fit.",
        ],
    }


def _default_scenarios():
    def triple(low, mode, high):
        return {"low": low, "mode": mode, "high": high}

    shared = {
        "runtime_seconds": triple(60, 120, 300),
        "system_watts": triple(30, 60, 120),
        "electricity_price_per_kwh": triple(4, 8, 16),
        "hardware_capital_cost": triple(300, 900, 1800),
        "amortization_months": triple(24, 36, 48),
        "scheduled_hours_per_month": triple(80, 140, 176),
        "availability_fraction": triple(0.65, 0.8, 0.95),
    }
    return [
        {
            "scenario_id": "conservative_assumptions",
            "inputs": {
                **shared,
                "encounters_per_active_hour": triple(0.5, 1, 1.5),
                "daily_demand_encounters": triple(2, 6, 12),
            },
        },
        {
            "scenario_id": "middle_assumptions",
            "inputs": {
                **shared,
                "encounters_per_active_hour": triple(1, 2, 3),
                "daily_demand_encounters": triple(8, 16, 28),
            },
        },
        {
            "scenario_id": "higher_load_assumptions",
            "inputs": {
                **shared,
                "encounters_per_active_hour": triple(1.5, 3, 5),
                "daily_demand_encounters": triple(20, 40, 70),
            },
        },
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--iterations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20261114)
    args = parser.parse_args()
    result = simulate(_default_scenarios(), iterations=args.iterations, seed=args.seed)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
