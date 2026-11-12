from services.note_style import apply


def test_note_style_preserves_statements_and_evidence():
    note = {
        "statements": [
            {"text": "No allergy.", "fact_ids": ["f1"], "evidence_ids": ["e1"]}
        ]
    }
    result = apply(note, "concise")
    assert result["style"] == "concise"
    assert result["statements"] == note["statements"]
    assert result["source_facts_preserved"] and result["evidence_preserved"]
    assert result["semantic_mutation"] is False
