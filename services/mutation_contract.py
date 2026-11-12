"""Deterministic critical-safety mutation contract."""

MUTANTS = ("dose_swap", "negation_flip", "stale_approval", "cross_tenant")


def evaluate(mutant, guard_result):
    if mutant not in MUTANTS:
        raise ValueError("unknown_safety_mutant")
    if guard_result is not False:
        raise ValueError("safety_mutant_bypass_detected")
    return {"mutant": mutant, "blocked": True, "real_patient_release_authorized": False}
