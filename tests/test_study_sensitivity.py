import pytest

from services.study_sensitivity import simulate_paired_binary_sensitivity


def _run(effect=0.08, sizes=(50, 150), seed=19):
    baseline_only = 0.12
    candidate_only = baseline_only + effect
    both = 0.05
    neither = 1 - baseline_only - candidate_only - both
    return simulate_paired_binary_sensitivity(
        sample_sizes=list(sizes),
        baseline_only_probability=baseline_only,
        candidate_only_probability=candidate_only,
        neither_probability=neither,
        both_probability=both,
        iterations=1500,
        seed=seed,
    )


def test_sensitivity_simulation_is_deterministic_and_labeled_hypothetical():
    first = _run()
    assert first == _run()
    assert first["study_performed"] is False
    assert first["evidence_class"] == "hypothetical_sensitivity_simulation"
    assert (
        first["sample_size_sensitivity"][1]["simulated_power"]
        >= first["sample_size_sensitivity"][0]["simulated_power"]
    )


def test_stronger_assumed_effect_increases_simulated_sensitivity():
    assert (
        _run(effect=0.16)["sample_size_sensitivity"][-1]["simulated_power"]
        >= _run(effect=0.02)["sample_size_sensitivity"][-1]["simulated_power"]
    )


def test_simulation_rejects_invalid_probability_mass_or_too_few_iterations():
    with pytest.raises(ValueError, match="sum_to_one"):
        simulate_paired_binary_sensitivity(
            sample_sizes=[20],
            baseline_only_probability=0.1,
            candidate_only_probability=0.1,
            neither_probability=0.1,
            both_probability=0.1,
            iterations=1000,
        )
    with pytest.raises(ValueError, match="configuration"):
        simulate_paired_binary_sensitivity(
            sample_sizes=[20],
            baseline_only_probability=0.1,
            candidate_only_probability=0.1,
            neither_probability=0.7,
            both_probability=0.1,
            iterations=10,
        )
