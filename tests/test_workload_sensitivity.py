import pytest

from services.workload_sensitivity import _default_scenarios, simulate


def test_assumption_only_workload_simulation_is_seeded_and_bounds_demand():
    args = (_default_scenarios(),)
    first = simulate(*args, iterations=1200, seed=91)
    assert first == simulate(*args, iterations=1200, seed=91)
    assert first["evidence_class"] == "hypothetical_assumption_only_monte_carlo"
    assert first["measured_inputs"] is False
    assert first["clinical_outcomes_inferred"] is False
    assert first["product_market_fit_inferred"] is False
    conservative, middle, high = first["results"]
    assert (
        conservative["outputs"]["capacity_encounters_per_day"]["p50"]
        < middle["outputs"]["capacity_encounters_per_day"]["p50"]
        < high["outputs"]["capacity_encounters_per_day"]["p50"]
    )
    for scenario in first["results"]:
        outputs = scenario["outputs"]
        assert (
            outputs["completed_encounters_per_day"]["p50"]
            <= min(
                outputs["capacity_encounters_per_day"]["p50"],
                outputs["demand_encounters_per_day"]["p50"],
            )
            + 1e-9
        )
        assert outputs["estimated_compute_cost_per_encounter"]["p05"] >= 0


def test_workload_simulation_rejects_bad_scenario_inputs_and_iteration_counts():
    with pytest.raises(ValueError, match="configuration"):
        simulate(_default_scenarios(), iterations=999)
    scenarios = _default_scenarios()
    scenarios[0]["inputs"]["availability_fraction"] = {
        "low": 0.8,
        "mode": 0.7,
        "high": 0.9,
    }
    with pytest.raises(ValueError, match="triangular_assumption"):
        simulate(scenarios, iterations=1000)
