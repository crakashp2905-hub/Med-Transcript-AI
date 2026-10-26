"""Retrospective rule comparison; development fixtures never become independent gold."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from services.review.clinical import check_claim
from services.verification_challenge import confusion


def run(output):
    out=Path(output)
    if out.exists():raise ValueError('Preserve prior evidence')
    baseline=subprocess.run(['git','show','c8a6636:services/review/clinical.py'],check=True,capture_output=True).stdout
    namespace={};exec(compile(baseline,'baseline_clinical.py','exec'),namespace)
    rows=[];sources={}
    for name in ('clinical-challenge-unseen-v1.json','clinical-challenge-relational-v1.json','clinical-challenge-relations-v2.json'):
        path=Path('evaluation')/name;sources[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        for case in json.loads(path.read_text())['cases']:
            old=namespace['check_claim'](case['source'],case['claim']);new=check_claim(case['source'],case['claim'])
            rows.append({**case,'cohort':name,'baseline_unsafe':bool(old),'updated_unsafe':bool(new),'baseline_findings':old,'updated_findings':new})
    result={'schema_version':'relationship_rule_comparison_v1','scope':'retrospective_development_comparison_not_independent_acceptance',
        'baseline_commit':'c8a6636','baseline_source_sha256':hashlib.sha256(baseline).hexdigest(),
        'current_source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ('services/review/clinical.py','services/review/relationships.py')},
        'cohort_sha256':sources,'cases':rows,'summary':{'baseline':confusion(rows,'baseline_unsafe'),'updated':confusion(rows,'updated_unsafe')},
        'cohorts':{name:{'baseline':confusion([r for r in rows if r['cohort']==name],'baseline_unsafe'),'updated':confusion([r for r in rows if r['cohort']==name],'updated_unsafe')} for name in sources},
        'cannot_clear_existing_findings':True,'clinical_acceptance':False,'complete':True}
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result['summary']))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args();run(args.out)
