from services.asr.postprocess import suggest


def test_postprocessor_keeps_raw_negation_and_dose_separate_from_suggestions():
    raw = [{'text': 'Patient denies warfarin 0.5 mg', 'uncertainties': ['unreviewed_asr']}]
    result = suggest(raw, [{'segment_index': 0, 'suggested_text': 'Patient denies warfarin 5 mg', 'reason': 'review'}])
    assert result['raw_segments'][0]['text'] == raw[0]['text']
    assert result['correction_suggestions'][0]['suggested_text'].endswith('5 mg')
    assert result['postprocessing_status'] == 'advisory_only'
