import pytest

from services.mutation_contract import MUTANTS, evaluate


def test_all_critical_mutants_require_a_blocked_guard_result():
    for mutant in MUTANTS:
        assert evaluate(mutant, False)["blocked"] is True
    with pytest.raises(ValueError, match="safety_mutant_bypass_detected"):
        evaluate("dose_swap", True)
    with pytest.raises(ValueError, match="unknown_safety_mutant"):
        evaluate("prompt_injection", False)
