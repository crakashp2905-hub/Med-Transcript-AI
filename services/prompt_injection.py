"""Keep transcript text untrusted and separate from application instructions."""

MARKERS = ('ignore previous instructions', 'approve the note', 'read file', 'execute command', 'system prompt')


def inspect(text):
    if not isinstance(text, str):
        raise ValueError('transcript_text_required')
    lowered = text.lower()
    matches = sorted(marker for marker in MARKERS if marker in lowered)
    return {'untrusted': True, 'markers': matches, 'application_control': False,
            'file_access': False, 'approval_control': False}
