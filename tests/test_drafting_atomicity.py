from services.review.providers import DeterministicProvider, validate


def test_deterministic_draft_keeps_each_reviewed_assertion_atomic():
    facts = [
        {
            "fact_id": "symptom-1",
            "section": "subjective",
            "text": "Patient reports cough.",
            "reviewed": True,
        },
        {
            "fact_id": "medication-1",
            "section": "plan",
            "text": "Continue warfarin 5 mg daily.",
            "reviewed": True,
        },
    ]

    result = DeterministicProvider().draft(facts, authorized=True, synthetic=True)

    statements = result["draft"]["statements"]
    assert [statement["fact_ids"] for statement in statements] == [
        ["symptom-1"],
        ["medication-1"],
    ]
    assert [statement["text"] for statement in statements] == [
        "Patient reports cough.",
        "Continue warfarin 5 mg daily.",
    ]
    assert result["findings"] == []


def test_combined_assertions_are_flagged_for_clinician_review():
    facts = [
        {
            "fact_id": "symptom-1",
            "section": "subjective",
            "text": "Patient reports cough.",
            "reviewed": True,
        },
        {
            "fact_id": "medication-1",
            "section": "plan",
            "text": "Continue warfarin 5 mg daily.",
            "reviewed": True,
        },
    ]

    result = validate(
        {
            "statements": [
                {
                    "section": "subjective",
                    "text": "Patient reports cough and continue warfarin 5 mg daily.",
                    "fact_ids": ["symptom-1", "medication-1"],
                }
            ]
        },
        facts,
    )

    assert any(
        finding["code"] == "merged_facts_requires_atomic_review"
        and finding["blocks_approval"]
        for finding in result["findings"]
    )
