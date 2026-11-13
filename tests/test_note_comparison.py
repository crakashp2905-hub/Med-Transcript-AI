from services.review.comparison import compare


def note(note_id, facts):
    return {
        "id": note_id,
        "transcript_version_id": "transcript-v1",
        "facts": facts,
    }


def test_dose_change_is_explicitly_marked_clinically_critical():
    before = {"fact_id": "f1", "text": "Take warfarin", "dose_value": "2.5"}
    after = {**before, "dose_value": "5"}

    result = compare(note("n1", [before]), note("n2", [after]))

    assert result["changes"][0]["change"] == "changed"
    assert result["changes"][0]["clinical_critical"] is True
    assert result["changes"][0]["critical_reasons"] == ["dose_value"]


def test_added_and_removed_negated_clinical_claims_are_marked_critical():
    fact = {
        "fact_id": "f1",
        "text": "Patient denies fever",
        "category": "symptom",
        "assertion": "negated",
        "evidence": {"segment_id": "s1"},
    }

    added = compare(note("n1", []), note("n2", [fact]))
    removed = compare(note("n1", [fact]), note("n2", []))

    assert added["changes"][0]["change"] == "added"
    assert added["changes"][0]["clinical_critical"] is True
    assert removed["changes"][0]["change"] == "removed"
    assert removed["changes"][0]["clinical_critical"] is True
