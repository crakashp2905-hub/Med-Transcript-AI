from services.role_guard import guard_role_claim


def test_low_confidence_role_is_unknown_and_blocks_claim():
    result = guard_role_claim(
        {"role": "clinician", "role_status": "unconfirmed"}, "medication_plan"
    )
    assert result["allowed"] is False and result["role"] == "unknown"


def test_confirmed_role_allows_claim():
    result = guard_role_claim(
        {"role": "clinician", "role_status": "clinician_confirmed"}, "medication_plan"
    )
    assert result["allowed"] is True and result["reason"] is None
