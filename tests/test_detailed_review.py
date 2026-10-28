import pytest
from services.detailed_review_materials import summarize


def test_empty_three_arm_study_does_not_invent_timing_or_cost():
    value=summarize({'protocol_sha256':'a'*64,'planned_pairs':['one','two'],'observations':[]})
    assert value['missing_conditions']==6 and value['observed_conditions']==0
    assert value['comparisons']['local_qwen']['median_seconds_saved_complete_pairs_only'] is None
    assert value['cost_totals']['provider_cost_usd'] is None and value['clinical_acceptance'] is False


def test_paired_summary_retains_failed_and_missing_arms():
    def row(arm,seconds):return {'pair_id':'one','arm':arm,'status':'complete','wall_seconds':seconds,'active_edit_seconds':seconds/2,'independently_adjudicated_critical_errors':0,'independently_adjudicated_omissions':1,'provider_cost_usd':0,'hardware_cost_usd':None}
    document={'protocol_sha256':'b'*64,'planned_pairs':['one','two'],'observations':[row('manual',120),row('deterministic',80),{'pair_id':'one','arm':'local_qwen','status':'failed'}]}
    value=summarize(document)
    assert value['failed_conditions']==1 and value['missing_conditions']==3
    assert value['comparisons']['deterministic']['median_seconds_saved_complete_pairs_only']==40
    assert value['comparisons']['local_qwen']['complete_pairs']==0
    document['observations'].append(row('manual',10))
    with pytest.raises(ValueError):summarize(document)
