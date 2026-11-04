import random
import pytest
from services.error_taxonomy import alignment,analyze,csv_cell
from services.evaluation import distance
from services.detailed_benchmark import fast_score


def test_exact_bitvector_traceback_matches_independent_dp_and_reconstructs_tokens():
    rng=random.Random(20261104);words=['no','not','0.5','5','mg','mcg','warfarin','um','cough']
    for _ in range(500):
        a=rng.choices(words,k=rng.randrange(25));b=rng.choices(words,k=rng.randrange(25))
        ops=alignment(a,b)
        assert sum(op!='match' for op,_,_ in ops)==distance(a,b)
        assert [a[i] for _,i,_ in ops if i is not None]==a
        assert [b[j] for _,_,j in ops if j is not None]==b
        assert all(a[i]==b[j] for op,i,j in ops if op=='match')


def test_role_uncertainty_buckets_do_not_change_primary_denominator_or_invent_speaker():
    text='Um no allergy.';hyp='No allergy extra.'
    case={'reference_turns':[{'reference':text,'role':'doctor','start_ms':0,'end_ms':1000,'uncertain_reference':True}]}
    row={'id':'case','reference':text,'hypothesis':hyp,'failed':False,**fast_score(text,hyp)}
    summary,errors=analyze(row,case)
    assert summary['normalized_edits']==2 and summary['reference_words']==3
    assert summary['reference_role_counts']['clinician']['reference_words']==3
    assert any(e['reference_role']=='unattributed_insertion' for e in errors)
    assert summary['predicted_speaker_accuracy_measured'] is False
    assert all(e['uncertain_reference_turn'] for e in errors if e['reference_index'] is not None)
    row['normalized_edits']=0
    with pytest.raises(ValueError):analyze(row,case)


def test_failed_case_retains_all_deletions_and_csv_formula_is_escaped():
    text='Warfarin 0.5 mg.';row={'id':'failed','reference':text,'hypothesis':'','failed':True,**fast_score(text,'')}
    case={'reference_turns':[{'reference':text,'role':'patient','start_ms':0,'end_ms':1000}]}
    result,errors=analyze(row,case)
    assert result['normalized_wer']==1 and len(errors)==result['reference_words']
    assert result['raw_cer']==1
    assert csv_cell('=unsafe')=="'=unsafe" and csv_cell('0.5 mg')=='0.5 mg'
