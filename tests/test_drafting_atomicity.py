from uuid import uuid4

from services.review.providers import DeterministicProvider, validate
from services.review.clinical import extract
from services.review.engine import render_sections


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


def test_unknown_allergy_and_examination_are_never_autofilled():
    facts = extract(
        {"segments": [{"segment_id": str(uuid4()), "text": "Patient reports cough."}]}
    )
    for fact in facts:
        fact["reviewed"] = True

    draft = DeterministicProvider().draft(facts, authorized=True, synthetic=True)
    statements = [item["text"].casefold() for item in draft["draft"]["statements"]]

    assert statements == ["patient reports cough."]
    assert not any("allerg" in statement for statement in statements)
    assert not any("normal examination" in statement for statement in statements)


def test_explicit_no_known_allergies_remains_tied_to_source():
    facts = extract(
        {"segments": [{"segment_id": str(uuid4()), "text": "No known allergies."}]}
    )
    for fact in facts:
        fact["reviewed"] = True

    draft = DeterministicProvider().draft(facts, authorized=True, synthetic=True)

    assert [item["text"] for item in draft["draft"]["statements"]] == [
        "No known allergies."
    ]


def test_soap_sections_preserve_only_supplied_facts_without_differentials():
    facts = [
        {
            "fact_id": "subjective-1",
            "section": "subjective",
            "text": "Patient reports cough.",
            "reviewed": True,
            "origin": "source_linked",
            "evidence": {
                "segment_id": "source-1",
                "start_char": 0,
                "end_char": 22,
                "quote": "Patient reports cough.",
            },
        },
        {
            "fact_id": "objective-1",
            "section": "objective",
            "text": "Temperature 37 C.",
            "reviewed": True,
            "origin": "source_linked",
            "evidence": {
                "segment_id": "source-1",
                "start_char": 23,
                "end_char": 40,
                "quote": "Temperature 37 C.",
            },
        },
        {
            "fact_id": "assessment-1",
            "section": "assessment",
            "text": "Assessment: cough.",
            "reviewed": True,
            "origin": "source_linked",
            "evidence": {
                "segment_id": "source-1",
                "start_char": 41,
                "end_char": 59,
                "quote": "Assessment: cough.",
            },
        },
        {
            "fact_id": "plan-1",
            "section": "plan",
            "text": "Follow up next week.",
            "reviewed": True,
            "origin": "source_linked",
            "evidence": {
                "segment_id": "source-1",
                "start_char": 60,
                "end_char": 80,
                "quote": "Follow up next week.",
            },
        },
    ]

    draft = DeterministicProvider().draft(facts, authorized=True, synthetic=True)
    sections = render_sections(facts, "transcript-1")

    assert [section["key"] for section in sections] == [
        "subjective",
        "objective",
        "assessment",
        "plan",
    ]
    assert [item["section"] for item in draft["draft"]["statements"]] == [
        "subjective",
        "objective",
        "assessment",
        "plan",
    ]
    text = " ".join(item["text"].casefold() for item in draft["draft"]["statements"])
    assert "pneumonia" not in text and "differential" not in text
    assert all(
        statement["source_version_id"] == "transcript-1"
        and statement["evidence"] is not None
        for section in sections
        for statement in section["statements"]
    )
