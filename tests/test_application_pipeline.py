from uuid import uuid4

from services.application_pipeline import enrich_fact_proposal


def test_application_pipeline_uses_resource_graph_attribution_and_relationship_helpers():
    fact_id = str(uuid4())
    segment_id = str(uuid4())
    result = enrich_fact_proposal(
        transcript_id=str(uuid4()),
        facts=[{'fact_id': fact_id, 'text': 'Patient denies left knee pain',
                'evidence': {'segment_id': segment_id, 'start_char': 0, 'end_char': 28}}],
        relationships={'relations': []},
    )
    enriched = result['facts'][0]
    assert result['resource_admission']['action'] == 'admit'
    assert result['application_pipeline'] == 'clinical_review_v1'
    assert enriched['attribution']['assertion'] == 'denied'
    assert enriched['evidence_graph']['complete'] is True
    assert enriched['anatomy_relations']['relations'][0]['laterality'] == 'left'
