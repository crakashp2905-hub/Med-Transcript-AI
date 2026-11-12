from services.terminology_hints import apply_hints


def test_terminology_hints_are_opt_in_and_non_mutating():
    text = "Patient denies warfarin."
    assert apply_hints(text)["text"] == text
    result = apply_hints(text, enabled=True)
    assert result["text"] == text
    assert result["matched_terms"] == ["warfarin"]
    assert result["medication_hallucination_risk"] == "requires_review"
