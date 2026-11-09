"""Require separate ASR corpus result groups."""

CORPORA = frozenset({'short_clip', 'three_long', 'meddistract_audio'})


def validate_separate(results):
    if isinstance(results, dict) and 'universal_wer' in results:
        raise ValueError('universal_wer_forbidden')
    if not isinstance(results, dict) or set(results) != CORPORA:
        raise ValueError('corpus_partition_required')
    return {'corpora': {name: results[name] for name in sorted(CORPORA)}, 'separate': True}
