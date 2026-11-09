"""Non-destructive ASR suggestions; raw segments are never overwritten."""


def suggest(raw_segments, suggestions=None):
    if not isinstance(raw_segments, list):
        raise ValueError('raw_segments_required')
    suggestions = suggestions or []
    return {
        'raw_segments': [dict(segment) for segment in raw_segments],
        'correction_suggestions': [dict(item) for item in suggestions],
        'postprocessing_status': 'advisory_only',
        'preserves_source_words': True,
    }
