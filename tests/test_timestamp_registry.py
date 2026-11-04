import pytest
from services.asr.timestamps import capability,check_segments


def test_text_only_and_native_chunk_capabilities_never_claim_word_alignment():
    assert capability('omi').kind=='none'
    assert capability('whisper',False).kind=='chunk'
    assert capability('whisper',True).kind=='segment'
    assert capability('unknown').kind=='none'
    assert capability('whisper',True).word_alignment_validated is False


def test_timestamp_bounds_order_duplicates_and_gaps_are_explicit():
    good=check_segments([{'start_ms':100,'end_ms':500,'text':'source'}],1000)
    assert good['bounds_and_order_valid'] and len(good['gaps'])==2
    bad=check_segments([{'start_ms':500,'end_ms':1001,'text':'a'},{'start_ms':0,'end_ms':100,'text':'b'},{'start_ms':0,'end_ms':100,'text':'b'}],1000)
    assert {i['code'] for i in bad['issues']}>={'timestamp_out_of_bounds','timestamp_order_reversed','duplicate_segment'}
    assert bad['word_alignment_validated'] is False
    with pytest.raises(ValueError):check_segments([],0)
