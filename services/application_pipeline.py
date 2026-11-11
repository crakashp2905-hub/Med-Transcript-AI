"""Validate source-linked analysis before a clinical proposal is persisted."""

from services.clinical_attribution import classify
from services.evidence_graph import validate_proposal
from services.relation_tuples import validate as validate_relations


def enrich_fact_proposal(*, transcript, facts, relationships):
    graph = validate_proposal(transcript, facts)
    checked = validate_relations(relationships['relations'])
    if not checked['all_valid']:
        raise ValueError('clinical_relationship_output_rejected')
    validate_proposal(transcript, [
        {'fact_id': f'relationship:{i}', 'evidence': row['evidence']}
        for i, row in enumerate(checked['relations'])
    ])
    return {'evidence_graph': graph, 'relation_validation': checked,
            'attribution': [{'fact_id': f['fact_id'], **classify(f['text'])} for f in facts],
            'application_pipeline': 'source_validated_clinical_review_v2'}
