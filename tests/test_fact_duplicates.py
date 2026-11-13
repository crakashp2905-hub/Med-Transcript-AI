from services.fact_duplicates import detect


def test_duplicate_fact_detection_preserves_temporal_or_contradictory_assertions():
    facts = [
        {
            "fact_id": "past-1",
            "category": "medication",
            "concept": "warfarin",
            "text": "Warfarin stopped",
            "temporality": "historical",
            "evidence": {
                "segment_id": "s1",
                "start_char": 0,
                "end_char": 15,
                "quote": "Warfarin stopped",
            },
        },
        {
            "fact_id": "current-1",
            "category": "medication",
            "concept": "warfarin",
            "text": "Warfarin stopped",
            "temporality": "current",
            "evidence": {
                "segment_id": "s2",
                "start_char": 0,
                "end_char": 15,
                "quote": "Warfarin stopped",
            },
        },
        {
            "fact_id": "plan-1",
            "category": "medication",
            "concept": "warfarin",
            "text": "Warfarin restarted",
            "temporality": "planned",
        },
    ]
    result = detect(facts)
    assert result["count"] == 1 and result["preserved_facts"] == 3
    assert result["contradictions_retained"] is True
    group = result["groups"][0]
    assert group["fact_ids"] == ["past-1", "current-1"]
    assert group["temporal_variants"] == ["current", "historical"]
    assert group["temporal_conflict"] is True
    assert group["automatic_suppression"] is False
    assert group["clinician_review_required"] is True
    assert result["raw_source_text_included"] is False
    assert {
        row["evidence_reference"]["segment_id"] for row in group["occurrences"]
    } == {
        "s1",
        "s2",
    }
