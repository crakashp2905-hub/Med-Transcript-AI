"""Frozen new-case rule/model comparison; no policy tuning during the run."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from uuid import NAMESPACE_URL, uuid5
from services.review.clinical import check_claim
from services.review.clinical_models import LocalClinicalModels,MODEL_DIGESTS


def confusion(rows, field):
    return {'attempted':len(rows),
            'critical_misses':sum(r['unsafe'] and r[field] is not True for r in rows),
            'omission_misses':sum(r['category']=='omission' and r[field] is not True for r in rows),
            'false_alarms':sum(not r['unsafe'] and r[field] is True for r in rows),
            'correct_including_failures':sum(r[field] is not None and r[field]==r['unsafe'] for r in rows),
            'missing_verdicts':sum(r[field] is None for r in rows)}


def run(source, output, models):
    path=Path(source); body=path.read_bytes(); challenge=json.loads(body)
    if Path(output).exists(): raise ValueError('Preserve previous evidence; choose a new report')
    cases=challenge['cases']
    if len({c['id'] for c in cases})!=len(cases): raise ValueError('Duplicate challenge IDs')
    result={'schema_version':'verification_comparison_v1','challenge_sha256':hashlib.sha256(body).hexdigest(),
            'reference_status':challenge['scope'],'clinical_acceptance':False,
            'cannot_clear_approval_gates':True,'complete':False,'cases':[],
            'source_sha256':{name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in ('services/review/clinical.py','services/review/relationships.py','services/review/clinical_models.py')},
            'planned_local_models':MODEL_DIGESTS if models else {}}
    provider=LocalClinicalModels(enabled=models)
    for case in cases:
        findings=check_claim(case['source'],case['claim'])
        row={**case,'rule_findings':findings,'rules_unsafe':bool(findings),'model_unsafe':None,'combined_unsafe':bool(findings)}
        started=time.perf_counter()
        if models:
            try:
                verdict=provider.check_claims([{'fact_id':str(uuid5(NAMESPACE_URL,case['id'])),
                    'text':case['claim'],'evidence':case['source']}],authorized=True,synthetic=True)
                row['model_result']=verdict
                row['model_unsafe']=verdict['verdicts'][0]['label']!='supported'
                row['combined_unsafe']=bool(findings) or row['model_unsafe']
            except ValueError as exc:
                row['model_failure']=getattr(exc,'code','bounded_evidence_validation_failure')
                # Failure requires human review; it is not a valid model detection.
                row['combined_unsafe']=True
        row['wall_seconds']=time.perf_counter()-started
        result['cases'].append(row)
        Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(case['id'], 'model_failure',row.get('model_failure'),flush=True)
    result['complete']=True
    result['summary']={name:confusion(result['cases'],field) for name,field in
                       [('rules','rules_unsafe'),('model','model_unsafe'),('combined_review_policy','combined_unsafe')]}
    result['policy']='rule alert OR non-supported model OR model failure requires review; no model verdict clears rules'
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default='evaluation/clinical-challenge-unseen-v1.json')
    parser.add_argument('--out',required=True)
    parser.add_argument('--local-models',action='store_true')
    args=parser.parse_args();run(args.source,args.out,args.local_models)
