"""Hypothetical paired binary-outcome sensitivity simulation, not study evidence."""

import random
from statistics import NormalDist


def simulate_paired_binary_sensitivity(
    *,
    sample_sizes,
    baseline_only_probability,
    candidate_only_probability,
    neither_probability,
    both_probability,
    iterations=5000,
    alpha=0.05,
    seed=20261114,
):
    probabilities = (
        neither_probability,
        baseline_only_probability,
        candidate_only_probability,
        both_probability,
    )
    if (
        not isinstance(sample_sizes, (list, tuple))
        or not sample_sizes
        or any(type(size) is not int or size < 2 for size in sample_sizes)
        or len(set(sample_sizes)) != len(sample_sizes)
        or type(iterations) is not int
        or iterations < 1000
        or type(seed) is not int
        or not isinstance(alpha, (int, float))
        or not 0 < alpha < 1
    ):
        raise ValueError("invalid_sensitivity_simulation_configuration")
    if any(
        not isinstance(value, (int, float)) or not 0 <= value <= 1
        for value in probabilities
    ):
        raise ValueError("invalid_paired_outcome_probability")
    if abs(sum(probabilities) - 1) > 1e-9:
        raise ValueError("paired_outcome_probabilities_must_sum_to_one")
    rng = random.Random(seed)
    cutoff = NormalDist().inv_cdf(1 - alpha / 2)
    results = []
    for size in sorted(sample_sizes):
        significant = 0
        for _ in range(iterations):
            improvement = regression = 0
            for _ in range(size):
                draw = rng.random()
                if draw < baseline_only_probability:
                    improvement += 1
                elif draw < baseline_only_probability + candidate_only_probability:
                    regression += 1
            differences = regression - improvement
            mean = differences / size
            # Paired binary difference has sample variance from d in {-1, 0, 1}.
            sum_squares = regression + improvement
            variance = max(0.0, (sum_squares - size * mean * mean) / (size - 1))
            standard_error = (variance / size) ** 0.5
            if standard_error == 0:
                excludes_zero = mean != 0
            else:
                excludes_zero = abs(mean / standard_error) > cutoff
            significant += excludes_zero
        results.append(
            {"consultations": size, "simulated_power": significant / iterations}
        )
    return {
        "schema_version": "paired_binary_sensitivity_simulation_v1",
        "outcome": "paired_consultation_binary_critical_miss",
        "paired_outcome_probabilities": {
            "neither_misses": neither_probability,
            "baseline_misses_candidate_does_not": baseline_only_probability,
            "candidate_misses_baseline_does_not": candidate_only_probability,
            "both_miss": both_probability,
        },
        "assumed_candidate_minus_baseline_miss_rate": candidate_only_probability
        - baseline_only_probability,
        "alpha_two_sided": alpha,
        "iterations_per_size": iterations,
        "seed": seed,
        "sample_size_sensitivity": results,
        "evidence_class": "hypothetical_sensitivity_simulation",
        "study_performed": False,
        "clinical_power_claim": False,
        "limitations": [
            "Paired outcome probabilities are user-supplied assumptions, not estimates from a clinical cohort.",
            "Consultations are assumed independent; reviewer adjudication and missingness are not modeled.",
            "The simulation does not establish efficacy, safety or the adequacy of a future study design.",
        ],
    }
