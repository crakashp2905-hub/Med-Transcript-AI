from datetime import datetime, timedelta, timezone
import json
import pytest
from services.experiment_contract import ExperimentContract, PRIMARY_ENDPOINTS, freeze, load_frozen, assess, variant_admission


def contract():
    return dict(experiment_id='prospective-synthetic-v1',frozen_at=datetime.now(timezone.utc)-timedelta(seconds=2),
                cohort='developer_synthetic',case_ids=['a','b','c'],primary_endpoints=PRIMARY_ENDPOINTS,
                dataset_sha256='a'*64,code_sha256='b'*64,configuration_sha256='c'*64,
                maximum_wall_seconds=60,minimum_complete_pairs=2,maximum_failure_fraction=.1,maximum_interval_width=.2)


def test_prospective_lock_rejects_posthoc_registration_and_changed_endpoint_or_gate(tmp_path):
    body=contract();path=tmp_path/'lock.json'
    with pytest.raises(ValueError):freeze(path,body,existing_results_present=True)
    for patch in ({'maximum_normalized_wer':.06},{'cohort':'independent_acceptance'},
                  {'primary_endpoints':{**PRIMARY_ENDPOINTS,'asr':'selected_successful_cases_wer'}},
                  {'case_ids':['a','a']},{'clinical_release':True}):
        with pytest.raises(ValueError):ExperimentContract.model_validate({**body,**patch})
    receipt=freeze(path,body)
    assert load_frozen(path,receipt['sha256']).case_ids==('a','b','c')
    with pytest.raises(FileExistsError):freeze(path,body)
    changed=json.loads(path.read_text());changed['maximum_wall_seconds']=600
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError):load_frozen(path,receipt['sha256'])


def test_missing_failed_timeout_and_unresolved_experiments_stay_inconclusive():
    body=ExperimentContract.model_validate(contract())
    now=datetime.now(timezone.utc)
    rows=[{'id':'a','status':'succeeded'},{'id':'b','status':'timed_out'}]
    result=assess(body,first_result_at=now,rows=rows,elapsed_seconds=61,complete_pairs=1,interval_width=None)
    assert set(result['reasons'])=={'missing_predeclared_cases','failure_budget_exceeded','wall_budget_exceeded','insufficient_complete_pairs','effect_unresolved'}
    assert result['case_statuses']==rows and not result['automatic_model_promotion']
    with pytest.raises(ValueError):assess(body,first_result_at=body.frozen_at-timedelta(seconds=1),rows=rows,elapsed_seconds=1,complete_pairs=2,interval_width=.1)
    with pytest.raises(ValueError):assess(body,first_result_at=now,rows=rows+rows,elapsed_seconds=1,complete_pairs=2,interval_width=.1)
    with pytest.raises(ValueError):assess(body,first_result_at=now,rows=rows,elapsed_seconds=1,complete_pairs=3,interval_width=.1)
    complete=[{'id':i,'status':'succeeded'} for i in body.case_ids]
    result=assess(body,first_result_at=now,rows=complete,elapsed_seconds=1,complete_pairs=3,interval_width=.1)
    assert result['status']=='eligible_for_prespecified_analysis' and not result['clinical_release']


def test_endpoint_registry_matches_contract_and_budget_stops_unevaluable_variants():
    from pathlib import Path
    registry=json.loads(Path('evaluation/primary-endpoint-registry-v1.json').read_text(encoding='utf-8'))
    assert {key:value['id'] for key,value in registry['endpoints'].items()}==PRIMARY_ENDPOINTS
    assert registry['endpoints']['ux']['current_observed_clinician_value'] is None
    body=contract()
    assert variant_admission(body,59)['status']=='admit'
    assert variant_admission(body,59.5)['status']=='stop_inconclusive'
    with pytest.raises(ValueError):variant_admission(body,float('nan'))
