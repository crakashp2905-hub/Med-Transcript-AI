from services.fact_duplicates import detect


def test_duplicate_fact_detection_preserves_temporal_or_contradictory_assertions():
    facts = [
        {
            "category": "medication",
            "concept": "warfarin",
            "text": "Warfarin stopped",
            "temporality": "historical",
        },
        {
            "category": "medication",
            "concept": "warfarin",
            "text": "Warfarin stopped",
            "temporality": "current",
        },
        {
            "category": "medication",
            "concept": "warfarin",
            "text": "Warfarin restarted",
            "temporality": "planned",
        },
    ]
    result = detect(facts)
    assert result["count"] == 1 and result["preserved_facts"] == 3
    assert result["contradictions_retained"] is True
