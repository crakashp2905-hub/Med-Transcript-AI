"""Explicit source-to-export evidence graph links."""

from services.canonical import content_sha256


def validate_proposal(transcript, facts):
    """Resolve real source IDs and exact quotes before building proposal edges."""
    audio_id = transcript.get('audio_asset_id')
    if not audio_id or not transcript.get('id'):
        raise ValueError('evidence_graph_source_required')
    segments = {s['segment_id']: s for s in transcript['segments']}
    if len(segments) != len(transcript['segments']):
        raise ValueError('evidence_graph_duplicate_segment')
    edges, seen = [], set()
    for fact in facts:
        fid = fact.get('fact_id')
        evidence = fact.get('evidence') or {}
        segment = segments.get(evidence.get('segment_id'))
        start, end = evidence.get('start_char'), evidence.get('end_char')
        if (not fid or fid in seen or segment is None or type(start) is not int
                or type(end) is not int or not 0 <= start < end <= len(segment['text'])
                or segment['text'][start:end] != evidence.get('quote')):
            raise ValueError('evidence_graph_invalid_source_link')
        seen.add(fid)
        span_id = content_sha256({'transcript': transcript['id'], 'evidence': evidence})
        edges.extend([
            {'from': str(audio_id), 'to': segment['segment_id'], 'type': 'audio_to_transcript'},
            {'from': segment['segment_id'], 'to': span_id, 'type': 'transcript_to_span'},
            {'from': span_id, 'to': fid, 'type': 'span_to_fact'},
        ])
    return {'edges': edges, 'transcript_version_id': transcript['id'],
            'source_sha256': content_sha256(transcript), 'facts_checked': len(facts),
            'complete_to_fact': True, 'complete_to_export': False,
            'clinical_release_authorized': False}


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
