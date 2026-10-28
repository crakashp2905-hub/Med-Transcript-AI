import hashlib
import random
import wave

import pytest

from services.detailed_benchmark import coverage,evaluate_case,fast_score,summarize
from services.evaluation import score
from services.prepare_detailed import select


def test_bitvector_token_scoring_matches_original_normalization_and_edit_counts():
    rng=random.Random(42);words=['0.5','5','mg','mcg','no','not','allergy','patient','mother',"don't",'5-mg']
    for _ in range(150):
        a=' '.join(rng.choices(words,k=rng.randrange(30)));b=' '.join(rng.choices(words,k=rng.randrange(30)))
        assert fast_score(a,b)==score(a,b)
    assert fast_score('no penicillin allergy 0.5 mg','penicillin allergy 5 mcg')['normalized_edits']==3


def test_detailed_selection_excludes_reserved_foreground_and_donor():
    rows=[{'item_id':'reserved','donor_id':'safe','level_db':-10},
        {'item_id':'safe','donor_id':'reserved','level_db':-10},
        {'item_id':'other','donor_id':'safe','level_db':-5},
        {'item_id':'eligible','donor_id':'safe','level_db':-10}]
    assert select(rows,{'reserved'},1)==[rows[-1]]
    with pytest.raises(ValueError):select(rows,{'reserved'},2)


def test_one_failed_window_retains_all_reference_deletions_and_raw_success(tmp_path):
    audio=tmp_path/'source.wav'
    with wave.open(str(audio),'wb') as out:out.setparams((1,2,16000,0,'NONE','not compressed'));out.writeframes(b'\0\0'*16000*31)
    case={'group_id':'full','foreground_id':'patient','condition':'clean','reference_turns':[{'reference':'No penicillin allergy.'}]}
    calls=[]
    def predict(path,context):
        calls.append(context)
        if len(calls)==2:raise RuntimeError('Synthetic native failure')
        return {'text':'No penicillin allergy.','segments':[{'start_ms':0,'end_ms':1000,'text':'No penicillin allergy.'}]}
    checkpoints=[];row=evaluate_case(case,audio,predict,'fixed',lambda current:checkpoints.append(len(current['chunks'])))
    assert row['failed'] and row['hypothesis']=='' and row['partial_hypothesis_for_diagnostics_only']=='No penicillin allergy.'
    assert row['normalized_edits']==row['reference_words']==3
    assert row['input_coverage_complete'] and checkpoints==[1,2]
    assert summarize([row])['wer_gate']['status']=='fail'
    assert not row['native_timestamp_bounds_valid']


def test_coverage_rejects_missing_prefix_gap_or_tail():
    assert coverage([(0,30),(28,50)],50)
    assert not coverage([(1,30),(28,50)],50)
    assert not coverage([(0,30),(31,50)],50)
    assert not coverage([(0,49)],50)
