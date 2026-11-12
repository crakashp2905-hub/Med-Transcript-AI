from services.turn_swap_guard import compare_claim_roles


def test_turn_swap_requires_warning_and_blocks_approval():
    result = compare_claim_roles(
        [{"claim_id": "c1", "role": "patient"}],
        [{"claim_id": "c1", "role": "clinician"}],
    )
    assert result["warnings"][0]["code"] == "semantic_role_swap"
    assert result["approval_blocked"] is True
