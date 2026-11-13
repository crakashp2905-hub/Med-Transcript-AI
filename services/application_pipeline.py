"""Validate source-linked analysis before a clinical proposal is persisted."""

from services.clinical_attribution import classify
from services.evidence_graph import validate_proposal
from services.fact_duplicates import detect as detect_duplicates
from services.relation_tuples import validate as validate_relations
from services.review.relationships import validate_graph


def enrich_fact_proposal(
    *, transcript, facts, relationships, relationship_transcript=None
):
    graph = validate_proposal(transcript, facts)
    relation_transcript = relationship_transcript or transcript
    relation_graph = validate_graph(relationships, relation_transcript)
    checked = validate_relations(relationships["relations"])
    if not checked["all_valid"]:
        raise ValueError("clinical_relationship_output_rejected")
    validate_proposal(
        transcript,
        [
            {"fact_id": f"relationship:{i}", "evidence": row["evidence"]}
            for i, row in enumerate(checked["relations"])
        ],
    )
    return {
        "evidence_graph": graph,
        "duplicate_analysis": detect_duplicates(facts),
        "relation_validation": checked,
        "relationship_graph_validation": relation_graph,
        "attribution": [
            {"fact_id": f["fact_id"], **classify(f["text"])} for f in facts
        ],
        "application_pipeline": "source_validated_clinical_review_v2",
    }
