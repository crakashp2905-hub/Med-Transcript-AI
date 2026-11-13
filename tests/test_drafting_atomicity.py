from uuid import uuid4

from services.review.providers import DeterministicProvider, validate
from services.review.clinical import extract
from services.review.engine import render_sections
from services.evidence_graph import validate_proposal


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


def test_statement_evidence_resolves_to_transcript_time_and_audio_asset():
    quote = "No fever."
    transcript = {
        "id": "transcript-v1",
        "audio_asset_id": "audio-v1",
        "segments": [
            {
                "segment_id": "segment-v1",
                "start_ms": 4200,
                "end_ms": 6100,
                "text": quote,
            }
        ],
    }
    evidence = {
        "segment_id": "segment-v1",
        "start_char": 0,
        "end_char": len(quote),
        "quote": quote,
    }
    fact = {
        "fact_id": "fact-v1",
        "section": "subjective",
        "text": quote,
        "origin": "source_linked",
        "evidence": evidence,
        "owner_clinician_id": None,
    }

    graph = validate_proposal(transcript, [fact])
    sections = render_sections([fact], transcript["id"])
    statement = sections[0]["statements"][0]

    assert statement["fact_ids"] == [fact["fact_id"]]
    assert statement["source_version_id"] == transcript["id"]
    assert statement["evidence"] == evidence
    assert transcript["segments"][0]["start_ms"] == 4200
    assert transcript["segments"][0]["end_ms"] == 6100
    assert graph["edges"] == [
        {"from": "audio-v1", "to": "segment-v1", "type": "audio_to_transcript"},
        {
            "from": "segment-v1",
            "to": graph["edges"][1]["to"],
            "type": "transcript_to_span",
        },
        {
            "from": graph["edges"][1]["to"],
            "to": fact["fact_id"],
            "type": "span_to_fact",
        },
    ]
