import pytest

from services.evaluation_method import score_findings


def test_critical_contradiction_blocks_even_when_scalar_weights_change():
    value = score_findings(
        [{"kind": "critical_contradiction"}],
        weights={"critical_contradiction": 0, "omission": 0, "false_block": 0},
    )
    assert value["scalar_cost"] == 0
    assert value["approval_gate"] == "blocked" and value["abstain"] is True


def test_omission_and_unresolved_are_explicit_and_unknown_kinds_fail_closed():
    value = score_findings([{"kind": "omission"}, {"kind": "unresolved"}])
    assert value["vector"] == {
        "critical_contradictions": 0,
        "omissions": 1,
        "false_blocks": 0,
        "unresolved": 1,
    }
    assert value["approval_gate"] == "blocked"
    with pytest.raises(ValueError, match="unknown_evaluation_finding"):
        score_findings([{"kind": "model_says_safe"}])
