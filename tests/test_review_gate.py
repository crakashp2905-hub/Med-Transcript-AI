from services.review_gate import evaluate


def test_review_gate_blocks_incomplete_and_ambiguous_cases():
    result = evaluate(["unknown_speaker", "ambiguous_medication_attachment"])
    assert result["review_required"] is True
    assert result["approval_allowed"] is False
    assert result["reasons"] == ["ambiguous_medication_attachment", "unknown_speaker"]
