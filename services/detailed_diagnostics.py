"""Reference-role and clinical lexical diagnostics; never adjudicated concept metrics."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import time

from services.api.ingest import file_sha256
from services.conversation_errors import analyze
from services.evaluation import tokens
from services.review.clinical import MEDICATION,QUANTITY,NEGATION


def mentions(pattern,text):return Counter(re.sub(r'\s+',' ',m.group().lower()) for m in pattern.finditer(text))


def lexical(reference,hypothesis):
    result={}
    for category,pattern in [('medication_names_finite_lexicon',MEDICATION),('dose_literal_value_unit',QUANTITY),
        ('allergy_words_not_allergy_assertions',re.compile(r'\ballerg(?:y|ies|ic)\b',re.I)),('negation_words_not_scope',NEGATION)]:
        a,b=mentions(pattern,reference),mentions(pattern,hypothesis)
        result[category]={'reference_mentions':sum(a.values()),'matched_mentions':sum((a&b).values()),
            'missing_mentions':dict(a-b),'extra_mentions':dict(b-a)}
    return result


def donor_matches(reference,hypothesis,donor,n=8):
    def grams(text):
        words=tokens(re.sub(r'\b(?:doctor|patient)\s*:','',text,flags=re.I))
        return {tuple(words[i:i+n]) for i in range(len(words)-n+1)}
    return [' '.join(g) for g in sorted((grams(donor)-grams(reference))&grams(hypothesis))][:30]


def run(manifest_path,report_path,output):
    manifest=json.loads(Path(manifest_path).read_text(encoding='utf-8'));report=json.loads(Path(report_path).read_text(encoding='utf-8'))
    if not report['complete'] or report['manifest_sha256']!=file_sha256(manifest_path):raise ValueError('Complete comparable report required')
    truth={c['group_id']:c for c in manifest['cases']};rows=[]
    for case in report['cases']:
        source=truth[case['id']];row=analyze(case,source['reference_turns'])
        row.update({'condition':case['condition'],'foreground_id':case['foreground_id'],
            'clinical_lexical':lexical(case['reference'],case['hypothesis']),
            'possible_donor_eight_token_matches':donor_matches(case['reference'],case['hypothesis'],source['donor_reference'])})
        rows.append(row)
    result={'schema_version':'detailed_reference_diagnostics_v1','manifest_sha256':file_sha256(manifest_path),'report_sha256':file_sha256(report_path),
        'candidate_id':report['candidate_id'],'mode':report['mode'],'cases':rows,'clinical_gold_available':False,'clinical_acceptance':False,
        'limitations':['Reference-role edit attribution is not predicted-speaker accuracy or word alignment.','Finite lexical counts do not establish medication/dose/allergy correctness or negation scope.','Token deletions are lexical omissions, not adjudicated clinical omissions.','Donor-only eight-token overlap is a diagnostic signal, not proof of clinical contamination.']}
    with Path(output).open('x',encoding='utf-8') as out:json.dump(result,out,indent=2);out.write('\n')
    return result


def watch(manifest,results,output,publish=False):
    root=Path(output);root.mkdir(parents=True,exist_ok=True)
    deadline=time.monotonic()+24*3600
    while time.monotonic()<deadline:
        for source in Path(results).glob('*.json'):
            destination=root/(source.stem+'.diagnostics.json')
            if destination.exists():continue
            report=json.loads(source.read_text(encoding='utf-8'))
            if not report.get('complete'):continue
            run(manifest,source,destination);print(str(destination),flush=True)
            if publish:
                subprocess.run(['git','add','--',str(destination)],check=True)
                subprocess.run(['git','commit','--only','-m',f'Record full-conversation role and clinical-term diagnostics: {source.stem}','--',str(destination)],check=False)
                subprocess.run(['git','push','origin','main'],check=False)
        suite_path=Path('evaluation/detailed-suite-v2.json');summary=Path('evaluation/reports/detailed-ranking-v2-2026-10-29.json')
        if suite_path.exists() and summary.exists():
            suite=json.loads(suite_path.read_text());ranked=json.loads(summary.read_text()).get('ranked',[])
            lookup={j['candidate_id']:j for j in suite['jobs']};weights=set();finalists=[]
            for row in ranked:
                cid=row['candidate_id'];job=lookup[cid];weight=job.get('model_dir',job.get('profile_id'))
                if weight not in weights:weights.add(weight);finalists.append(cid)
                if len(finalists)==2:break
            expected=[f'{j["candidate_id"]}.fixed' for j in suite['jobs']]
            for cid in finalists:
                modes=['overlap','speech_aware']+(['context'] if lookup[cid]['runtime']=='whisper' else [])
                expected.extend(f'{cid}.{mode}' for mode in modes)
            if len(ranked)==len(suite['jobs']) and all((root/f'{name}.diagnostics.json').exists() for name in expected):
                print('All baseline and finalist diagnostics complete.',flush=True);return
        time.sleep(30)
    raise RuntimeError('Diagnostics watch deadline reached; unfinished reports remain visible')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',default='evaluation/datasets/meddistract-detailed-v1/manifest.json');p.add_argument('--results',default='evaluation/runs/meddistract-detailed-v2');p.add_argument('--output',default='evaluation/reports/detailed-diagnostics-v2');p.add_argument('--watch',action='store_true');p.add_argument('--publish',action='store_true');p.add_argument('--report');a=p.parse_args()
    if a.watch:watch(a.manifest,a.results,a.output,a.publish)
    else:run(a.manifest,a.report,a.output)
