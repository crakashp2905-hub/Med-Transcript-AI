"""Resume/upload interruption transition matrix."""

TRANSITIONS = ('capture', 'indexeddb_commit', 'server_chunk_ack', 'finalize', 'ingest', 'asr_publication')


def matrix():
    return [{'transition': transition, 'resume_supported': True,
             'publication_allowed': transition == 'asr_publication'} for transition in TRANSITIONS]
