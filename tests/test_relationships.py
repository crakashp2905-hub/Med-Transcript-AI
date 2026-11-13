import json
import hashlib
from pathlib import Path
from uuid import uuid4
import pytest
from services.review.relationships import disagreement, analyze_transcript
from services.review.clinical import check_claim

CHALLENGE_PATH = Path("evaluation/clinical-challenge-relations-v3.json")
CHALLENGE = json.loads(CHALLENGE_PATH.read_text(encoding="utf-8"))
CASES = CHALLENGE["cases"]


def test_clinical_challenge_v3_preserves_its_predecessor_hash():
    previous = Path(CHALLENGE["supersedes"]["path"])

    assert previous.is_file()
    assert (
        hashlib.sha256(previous.read_bytes()).hexdigest()
        == CHALLENGE["supersedes"]["sha256"]
    )
    assert "not_independent_clinical_gold" in CHALLENGE["scope"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_changed_bindings_require_review_and_exact_controls_remain_clear(case):
    findings = check_claim(case["source"], case["claim"])
    assert bool(findings) == case["unsafe"]
    if case["unsafe"] and case["category"] != "omission":
        assert any(f["code"] == "clinical_relationship_disagreement" for f in findings)


def test_relationship_quotes_are_exact_and_never_reviewed():
    text = "Patient takes insulin 4 units before lunch and 8 units at bedtime."
    sid = str(uuid4())
    result = analyze_transcript({"segments": [{"segment_id": sid, "text": text}]})
    assert len(result["relations"]) == 2
    for row in result["relations"]:
        evidence = row["evidence"]
        assert evidence["quote"] == text[evidence["start_char"] : evidence["end_char"]]
        assert evidence["segment_id"] == sid
        assert row["review_required"] is True
    assert result["clinical_calibration"] is False
    assert result["schema_version"] == "explicit_relationship_graph_v2"
    for edge in result["edges"]:
        evidence = edge["evidence"]
        assert evidence["quote"] == text[evidence["start_char"] : evidence["end_char"]]
        assert edge["review_required"] is True


def test_typed_graph_links_medication_and_symptom_attributes_to_exact_evidence():
    text = (
        "Patient denies cough today. "
        "Patient takes warfarin 5 mg orally twice daily for five days."
    )
    sid = str(uuid4())
    result = analyze_transcript({"segments": [{"segment_id": sid, "text": text}]})

    edge_types = {edge["relation_type"] for edge in result["edges"]}
    node_values = {node["value"] for node in result["nodes"]}

    assert {
        "dose",
        "route",
        "frequency",
        "duration",
        "temporality",
        "subject",
        "negation",
    } <= edge_types
    assert {
        "warfarin",
        "5 mg",
        "oral",
        "twice daily",
        "five days",
        "cough",
        "today",
        "patient",
        "negated",
    } <= node_values
    assert all(edge["evidence"]["segment_id"] == sid for edge in result["edges"])
    assert all(edge["review_required"] for edge in result["edges"])
    assert all(node["node_id"] for node in result["nodes"])
    assert result["clinical_calibration"] is False


def test_repeated_identical_source_returns_stable_graph_ids():
    source = {"segments": [{"segment_id": str(uuid4()), "text": "No fever today."}]}

    first = analyze_transcript(source)
    second = analyze_transcript(source)

    assert [node["node_id"] for node in first["nodes"]] == [
        node["node_id"] for node in second["nodes"]
    ]
    assert first["edges"] == second["edges"]


def test_relation_graph_validator_rejects_unlinked_or_fabricated_edges():
    from services.review.relationships import validate_graph

    transcript = {
        "segments": [
            {"segment_id": str(uuid4()), "text": "Patient denies fever today."}
        ]
    }
    graph = analyze_transcript(transcript)
    validate_graph(graph, transcript)

    graph["edges"][0]["to_node_id"] = "unlinked-node"
    with pytest.raises(ValueError, match="clinical_relationship_edge_invalid"):
        validate_graph(graph, transcript)


def test_relation_graph_validator_rejects_typed_edge_mutation():
    from services.review.relationships import validate_graph

    transcript = {
        "segments": [
            {
                "segment_id": str(uuid4()),
                "text": "Patient takes warfarin 5 mg twice daily.",
            }
        ]
    }
    graph = analyze_transcript(transcript)
    dose_edge = next(edge for edge in graph["edges"] if edge["relation_type"] == "dose")
    dose_edge["relation_type"] = "route"

    with pytest.raises(
        ValueError, match="clinical_relationship_graph_content_mismatch"
    ):
        validate_graph(graph, transcript)


def test_clause_reordering_does_not_change_bindings():
    assert not disagreement("No cough. No fever.", "No fever. No cough.")
    assert not disagreement(
        "Take amoxicillin 250 mg orally.", "Take amoxicillin 250 mg by mouth."
    )


def test_structured_slots_cannot_borrow_another_drug_dose_or_reaction():
    from services.review.clinical import check_fact_slots, extract

    assert any(
        f["field"] == "dose_medication_relationship"
        for f in check_fact_slots(
            "Take amoxicillin 250 mg and warfarin 5 mg.",
            {"medication_name": "amoxicillin", "dose_value": "5", "dose_unit": "mg"},
        )
    )
    assert any(
        f["field"] == "allergy_reaction_relationship"
        for f in check_fact_slots(
            "Penicillin caused rash. Ibuprofen caused vomiting.",
            {"allergen": "penicillin", "allergy_reaction": "vomiting"},
        )
    )
    rows = extract(
        {
            "segments": [
                {
                    "segment_id": str(uuid4()),
                    "text": "Take amoxicillin 250 mg orally twice daily for five days.",
                }
            ]
        }
    )
    assert (
        rows[0]["route"] == "orally"
        and rows[0]["frequency"] == "twice daily"
        and rows[0]["duration"] == "five days"
    )
    assert rows[0]["reviewed"] is False
