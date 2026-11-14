import pytest

from services.draft_grounding_metrics import score_grounded_draft


def _fact(**overrides):
    return {
        "category": "medication",
        "concept": "warfarin",
        "subject": "patient",
        "assertion": "affirmed",
        "temporality": "current",
        "dose": "5",
        "unit": "mg",
    } | overrides


def test_draft_metrics_score_precision_recall_unsupported_and_dangerous_changes():
    sources = [
        {"id": "f1", "fact": _fact(), "material": True},
        {
            "id": "f2",
            "fact": {
                "category": "allergy",
                "concept": "penicillin",
                "assertion": "negated",
            },
            "material": True,
        },
    ]
    result = score_grounded_draft(
        sources,
        [
            {"fact": _fact(), "source_fact_ids": ["f1"]},
            {"fact": _fact(dose="10"), "source_fact_ids": ["f1"]},
            {
                "fact": {
                    "category": "allergy",
                    "concept": "penicillin",
                    "assertion": "affirmed",
                },
                "source_fact_ids": ["f2"],
            },
            {
                "fact": {"category": "diagnosis", "concept": "pneumonia"},
                "source_fact_ids": [],
            },
        ],
    )
    assert result["factual_precision"] == 0.25
    assert result["material_source_recall"] == 0.5
    assert result["unsupported_claim_count"] == 3
    assert result["dangerous_transformation_count"] == 2
    assert result["approval_effect"] == "none"


def test_unknown_citations_are_counted_as_unsupported():
    result = score_grounded_draft(
        [{"id": "f1", "fact": _fact(), "material": True}],
        [{"fact": _fact(), "source_fact_ids": ["missing"]}],
    )
    assert result["malformed_or_unknown_citation_claim_count"] == 1
    assert result["unsupported_claim_count"] == 1


def test_invalid_fact_and_duplicate_source_identity_fail_closed():
    with pytest.raises(ValueError, match="source_fact_invalid"):
        score_grounded_draft(
            [{"id": "f1", "fact": _fact()}, {"id": "f1", "fact": _fact()}], []
        )
