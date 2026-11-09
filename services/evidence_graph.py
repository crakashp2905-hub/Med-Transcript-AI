"""Explicit source-to-export evidence graph links."""


def build(*, audio_id, transcript_segment_id, evidence_span, fact_id, note_statement_id, export_id):
    values = (audio_id, transcript_segment_id, evidence_span, fact_id, note_statement_id, export_id)
    if any(not value for value in values):
        raise ValueError('evidence_graph_link_required')
    return {'edges': [
        {'from': audio_id, 'to': transcript_segment_id, 'type': 'audio_to_transcript'},
        {'from': transcript_segment_id, 'to': evidence_span, 'type': 'transcript_to_span'},
        {'from': evidence_span, 'to': fact_id, 'type': 'span_to_fact'},
        {'from': fact_id, 'to': note_statement_id, 'type': 'fact_to_note'},
        {'from': note_statement_id, 'to': export_id, 'type': 'note_to_export'},
    ], 'complete': True, 'clinical_release_authorized': False}
