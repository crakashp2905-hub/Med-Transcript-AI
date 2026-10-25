"""Reproducible synthetic rule/model checks; labels are developer-authored."""
import argparse
import json
from pathlib import Path
from uuid import NAMESPACE_URL,uuid5
from services.review.clinical import check_claim
from services.review.clinical_models import LocalClinicalModels

CASES=[
 ('dose_assignment','Taking metformin 500 mg and warfarin 5 mg.','Taking metformin 5 mg and warfarin 500 mg.',True),
 ('negation_scope','Patient denies fever but reports cough.','Patient reports fever but denies cough.',True),
 ('omission','Patient reports cough and fever.','Patient reports cough.',True),
 ('unit_conversion','Taking metformin 1000 mg.','Taking metformin 1 g.',False),
 ('decimal_conversion','Taking warfarin .005 g.','Taking warfarin 5 mg.',False),
 ('unchanged_allergy','Allergy to penicillin with rash.','Allergy to penicillin with rash.',False),
]


def run(output,models=False):
    result={'data_class':'synthetic','annotation_status':'developer_authored_not_clinician_calibrated','complete':False,
        'clinical_acceptance':False,'cases':[],'model_extraction':[],
        'scope':'small_development_regression_not_estimated_clinical_sensitivity'}
    provider=LocalClinicalModels(enabled=models)
    for name,source,claim,unsafe in CASES:
        findings=check_claim(source,claim)
        row={'id':name,'source':source,'claim':claim,'expected_unsafe':unsafe,
            'rule_findings':[f['code'] for f in findings],'rule_detected_unsafe':bool(findings)}
        if models:
            try:
                checked=provider.check_claims([{'fact_id':str(uuid5(NAMESPACE_URL,name)),'text':claim,'evidence':source}],authorized=True,synthetic=True)
                row['model_result']=checked
            except ValueError:
                row['model_failure']='bounded_failure_no_verdict_admitted'
        result['cases'].append(row)
        Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(name, 'rules_match=',bool(findings)==unsafe,'model_failed=',bool(row.get('model_failure')),flush=True)
    if models:
        for index,text in enumerate(['Patient reports cough and denies fever. Taking warfarin 5 mg.',
            'Mother has diabetes. Patient reports left knee pain. No drug allergies.']):
            transcript={'segments':[{'segment_id':str(uuid5(NAMESPACE_URL,f'extraction-{index}')),'text':text}]}
            try:
                extracted=provider.extract_facts(transcript,authorized=True,synthetic=True)
                row={'input':transcript,'result':extracted,'failed':False}
            except ValueError:
                row={'input':transcript,'failed':True,'error':'bounded_failure_no_facts_admitted'}
            result['model_extraction'].append(row)
            Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    result['rule_confusion']={
        name:sum((r['expected_unsafe'],r['rule_detected_unsafe'])==pair for r in result['cases'])
        for name,pair in [('true_positive',(True,True)),('false_positive',(False,True)),('true_negative',(False,False)),('false_negative',(True,False))]}
    result['model_failures']=sum('model_failure' in r for r in result['cases']) if models else None
    result['complete']=len(result['cases'])==len(CASES) and (not models or len(result['model_extraction'])==2)
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--local-models',action='store_true')
    p.add_argument('--out',default='evaluation/reports/completion-clinical-models-2026-10-25.json')
    a=p.parse_args();run(a.out,a.local_models)
