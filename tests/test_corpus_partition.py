import pytest

from services.corpus_partition import validate_separate


def test_corpus_results_remain_separate():
    result = validate_separate({'short_clip': {'wer': .1}, 'three_long': {'wer': .2}, 'meddistract_audio': {'wer': .3}})
    assert result['separate'] is True and set(result['corpora']) == {'short_clip', 'three_long', 'meddistract_audio'}


def test_corpus_partition_rejects_universal_wer():
    with pytest.raises(ValueError, match='universal_wer_forbidden'):
        validate_separate({'short_clip': {}, 'three_long': {}, 'meddistract_audio': {}, 'universal_wer': .2})
