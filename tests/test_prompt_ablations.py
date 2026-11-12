import pytest

from services.prompt_ablations import define


def test_prompt_ablations_are_separate_and_do_not_change_active_policy():
    result = define("grammar_constrained", prompt_digest="p1", input_digest="i1")
    assert result["active_model_policy_changed"] is False
    assert result["clinical_acceptance"] is False


def test_unknown_prompt_ablation_rejected():
    with pytest.raises(ValueError, match="unknown_prompt_ablation"):
        define("untracked", prompt_digest="p", input_digest="i")
