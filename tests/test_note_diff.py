from services.note_diff import compare


def test_note_diff_highlights_changed_meanings_omissions_and_extra_claims():
    result = compare(
        {"assessment": "stable", "plan": "continue"},
        {"assessment": "worse", "extra": "claim"},
    )
    assert result["changed_meanings"] == ["assessment"]
    assert result["omissions"] == ["plan"]
    assert result["extra_claims"] == ["extra"]
    assert result["approval_required"] is True
