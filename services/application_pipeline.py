"""Application-level composition of bounded clinical helper modules."""

import os

from services.anatomy_relations import extract as extract_anatomy
from services.clinical_attribution import classify
from services.evidence_graph import build as build_evidence_graph
from services.relation_tuples import validate as validate_relations
from services.resource_arbiter import decide as arbitrate_resources


def enrich_fact_proposal(*, transcript_id, facts, relationships):
    """Enrich a proposal before persistence; every helper result remains review-gated."""
    capacity = int(os.environ.get('MED_TRANSCRIPT_LOCAL_MEMORY_UNITS', '1'))
    admission = arbitrate_resources(active_bytes=0, request_bytes=1, capacity_bytes=capacity)
    if not admission['oversubscribed']:
        relation_rows = relationships.get('relations', []) if isinstance(relationships, dict) else []
        relation_check = validate_relations(relation_rows)
        enriched = []
        for fact in facts:
            quote = fact.get('text', '')
            evidence = fact.get('evidence') or {}
            attribution = classify(quote)
            anatomy = extract_anatomy(quote)
            graph = build_evidence_graph(
                audio_id=f"audio:{transcript_id}",
                transcript_segment_id=str(evidence.get('segment_id', transcript_id)),
                evidence_span=f"span:{evidence.get('segment_id', transcript_id)}:{evidence.get('start_char', 0)}:{evidence.get('end_char', 0)}",
                fact_id=str(fact.get('fact_id')),
                note_statement_id=f"statement:{fact.get('fact_id')}",
                export_id=f"pending-export:{fact.get('fact_id')}",
            )
            enriched.append({**fact, 'attribution': attribution, 'anatomy_relations': anatomy,
                             'evidence_graph': graph})
        return {'facts': enriched, 'relation_validation': relation_check,
                'resource_admission': admission, 'application_pipeline': 'clinical_review_v1'}
    return {'facts': facts, 'relation_validation': {'relations': [], 'invalid': [], 'all_valid': True},
            'resource_admission': admission, 'application_pipeline': 'deferred_for_memory'}
