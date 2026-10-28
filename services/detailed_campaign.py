"""Serial local full-recording campaign; incomplete/blocked candidates stay visible."""
import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

from services.api.ingest import file_sha256
from services.detailed_benchmark import fast_score,summarize
from services.inference_slot import local_inference_slot
from services.evidence_io import atomic_json


def source_hash(path):
    import hashlib
    return hashlib.sha256(Path(path).read_text(encoding='utf-8').encode('utf-8')).hexdigest()


def initialize(path,manifest='evaluation/datasets/meddistract-detailed-v1/manifest.json'):
    target=Path(path)
    if target.exists():raise ValueError('Preserve frozen suite')
    original=json.loads(Path('evaluation/expanded-suite-v1.json').read_text())
    qwen=json.loads(Path('evaluation/runs/primock57-expanded-v1/qwen3-asr-0.6b-int8.json').read_text())
    jobs=original['jobs']+[{'candidate_id':'qwen3-asr-0.6b-int8','runtime':'sherpa-qwen3',
        'model_dir':'data/models/sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25','revision':qwen['model_revision'],
        'package_dir':'data/diarization-runtime','expected_artifacts':qwen['runtime_configuration']['artifacts']}]
    omi=next(j for j in jobs if j['runtime']=='omi')
    jobs.append({**omi,'candidate_id':'omi-med-stt-v1-native-empty','allow_native_empty':True,
        'variant_note':'Same weights; exact documented native zero-token response accepted. All other errors remain failures.'})
    order=['faster-whisper-tiny.en','omi-med-stt-v1-native-empty','omi-med-stt-v1','whisper-small','multimed-whisper-small-english','parakeet-tdt-0.6b-v2','qwen3-asr-0.6b-int8','distil-whisper-large-v3','faster-whisper-large-v3']
    jobs.sort(key=lambda j:order.index(j['candidate_id']))
    for job in jobs:
        old=Path('evaluation/runs/meddistract-detailed-v1')/f'{job["candidate_id"]}.fixed.json'
        if old.exists() and json.loads(old.read_text()).get('cases'):job['resume_from']={'path':old.as_posix(),'sha256':file_sha256(old)}
    suite={'schema_version':'detailed_campaign_v1','manifest':manifest,'manifest_sha256':file_sha256(manifest),
        'audio_root':'data/datasets/meddistract-detailed-v1','maximum_normalized_wer':.05,'paid_calls_permitted':False,
        'primary_ranking':'all_eight_clean_full_consultations_micro_WER_then_paired_distracted_WER_then_latency',
        'models':8,'runtime_variants':9,'jobs':jobs,
        'ablations':{'selection':'two lowest clean WER completed fixed-window candidates, distinct weights','modes':['overlap','speech_aware'],
            'native_whisper_context':'run only when selected finalist uses Whisper; no context emulation for text-only adapters'},
        'timeout_per_candidate_seconds':14400,'clinical_release_authorized':False,
        'artifact_publication':'atomic_replace_with_bounded_Windows_reader_lock_retry_v2',
        'superseded_preinference_suite_sha256':file_sha256('evaluation/detailed-suite-v1.json'),
        'source_text_sha256':{name:source_hash(name) for name in ['services/detailed_benchmark.py','services/detailed_campaign.py','services/conversation_experiment.py','services/evaluation.py','services/omi_adapter.py','services/qwen_adapter.py','services/evidence_io.py']}}
    target.write_text(json.dumps(suite,indent=2)+'\n',encoding='utf-8');return suite


def bootstrap(rows,iterations=1000):
    rng=random.Random(20261029);ratios=[]
    if not rows:return None
    for _ in range(iterations):
        sample=rng.choices(rows,k=len(rows));ratios.append(sum(r['normalized_edits'] for r in sample)/sum(r['reference_words'] for r in sample))
    ratios.sort();return {'method':'foreground_cluster_percentile_bootstrap','iterations':iterations,'seed':20261029,
        'low':ratios[int(iterations*.025)],'high':ratios[min(iterations-1,int(iterations*.975))],
        'limitation':'Eight convenience-sampled development foregrounds; not a clinical acceptance confidence bound.'}


def ranking(suite,results,states=None):
    manifest=json.loads(Path(suite['manifest']).read_text(encoding='utf-8'))
    if file_sha256(suite['manifest'])!=suite['manifest_sha256']:raise ValueError('Frozen source changed')
    truth={c['group_id']:c for c in manifest['cases']};ranked=[];visible=[]
    for job in suite['jobs']:
        cid=job['candidate_id'];path=Path(results)/f'{cid}.fixed.json';state=(states or {}).get(cid,'queued')
        if not path.exists():visible.append({'candidate_id':cid,'status':state});continue
        report=json.loads(path.read_text(encoding='utf-8'));rows=report.get('cases',[])
        if report['manifest_sha256']!=suite['manifest_sha256']:raise ValueError('Incomparable report')
        if state=='queued':state='runtime_failed' if report.get('initialization_failure') else 'running_or_interrupted'
        progress={'candidate_id':cid,'status':state,'completed_recordings':len(rows),'total_recordings':len(truth),
            'active_case':None if not report.get('active_case') else {'id':report['active_case']['id'],'completed_chunks':len(report['active_case']['chunks'])}}
        if not report['complete']:visible.append(progress);continue
        if len(rows)!=len(truth) or {r['id'] for r in rows}!=set(truth):raise ValueError('Incomplete/duplicate comparison')
        for row in rows:
            case=truth[row['id']]
            import re
            reference=' '.join(re.sub(r'<[^>]+>','',t['reference']) for t in case['reference_turns'])
            if row['reference']!=reference or row['input_sha256']!=case['audio_sha256']:raise ValueError('Reference/input changed')
            expected=fast_score(reference,'' if row['failed'] else row['hypothesis'])
            if any(row[k]!=v for k,v in expected.items()):raise ValueError('Scoring changed')
        clean=[r for r in rows if r['condition']=='clean'];distracted=[r for r in rows if r['condition']=='distracted']
        if len(clean)!=8 or len(distracted)!=8:raise ValueError('Paired condition coverage changed')
        clean_summary=summarize(clean);noise_summary=summarize(distracted)
        ranked.append({'candidate_id':cid,'status':'complete','clean':clean_summary,'distracted':noise_summary,
            'paired_WER_delta':noise_summary['normalized_wer']-clean_summary['normalized_wer'],
            'clean_cluster_interval':bootstrap(clean),'native_segment_timestamps':report['runtime']['native_segment_timestamps'],
            'native_timestamp_bounds_valid':all(r['native_timestamp_bounds_valid'] for r in rows),
            'report_sha256':file_sha256(path),'clinical_approval':False})
    ranked.sort(key=lambda r:(Fraction(r['clean']['normalized_edits'],r['clean']['reference_words']),Fraction(r['distracted']['normalized_edits'],r['distracted']['reference_words']),r['clean']['wall_seconds']))
    for n,row in enumerate(ranked,1):row['rank']=n
    return {'schema_version':'detailed_ranking_v1','manifest_sha256':suite['manifest_sha256'],'ranked':ranked,'unranked':visible,
        'complete':len(ranked)==len(suite['jobs']),'maximum_normalized_wer':.05,'real_patient_release_authorized':False,
        'limitations':['Paired conditions share foregrounds; do not count them as independent patients.','Native segment bounds are not word alignment or verified timestamp accuracy.','One same-weight native-empty wrapper variant is separately labelled.','Incomplete or load-blocked models are visible and never assigned invented WER.']}


def run(suite_path,results,summary,publish=False):
    suite=json.loads(Path(suite_path).read_text());root=Path(results);root.mkdir(parents=True,exist_ok=True);states={}
    for name,sha in suite['source_text_sha256'].items():
        if source_hash(name)!=sha:raise ValueError('Frozen runner source changed before execution')
    def save():
        output=ranking(suite,root,states);path=Path(summary);path.parent.mkdir(parents=True,exist_ok=True)
        atomic_json(path,output)
        return output
    def job_run(cid,mode):
        path=root/f'{cid}.{mode}.json'
        if path.exists():
            old=json.loads(path.read_text(encoding='utf-8'))
            if old.get('complete') and old['manifest_sha256']==suite['manifest_sha256'] and old['suite_sha256']==file_sha256(suite_path):return
            raise ValueError('Preserve incomplete attempt; explicitly select a fresh results directory')
        states[cid]='running';save()
        with path.with_suffix('.log').open('w',encoding='utf-8') as log:
            while True:
                with local_inference_slot() as acquired:
                    if acquired:
                        command=[sys.executable,'-m','services.detailed_benchmark','--suite',suite_path,'--candidate',cid,'--output',str(path),'--mode',mode]
                        child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,start_new_session=os.name!='nt')
                        started=time.monotonic()
                        while child.poll() is None:
                            if time.monotonic()-started>suite['timeout_per_candidate_seconds']:
                                if os.name=='nt':subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],stdout=log,stderr=subprocess.STDOUT,check=False)
                                else:
                                    import signal
                                    os.killpg(child.pid,signal.SIGKILL)
                                child.wait();states[cid]='resource_timeout';break
                            save();time.sleep(5)
                        else:states[cid]='completed' if child.returncode==0 else 'runtime_failed'
                        break
                states[cid]='waiting_for_local_inference_slot';save();time.sleep(5)
        state=save();print(json.dumps({'candidate':cid,'mode':mode,'status':states[cid]}),flush=True)
        if publish:
            paths=[str(path),summary] if path.exists() else [summary]
            subprocess.run(['git','add','--',*paths],check=True)
            subprocess.run(['git','commit','-m',f'Record detailed full-consultation benchmark: {cid} {mode}'],check=False)
            subprocess.run(['git','push','origin','main'],check=False)
        return state
    for job in suite['jobs']:job_run(job['candidate_id'],'fixed')
    final=save();finalists=[];weights=set()
    lookup={j['candidate_id']:j for j in suite['jobs']}
    for row in final['ranked']:
        cid=row['candidate_id'];job=lookup[cid];key=job.get('model_dir',job.get('profile_id'))
        if key not in weights:weights.add(key);finalists.append(cid)
        if len(finalists)==2:break
    for cid in finalists:
        modes=suite['ablations']['modes']+(['context'] if lookup[cid]['runtime']=='whisper' else [])
        for mode in modes:job_run(cid,mode)
    save()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['init','run','status']);p.add_argument('--suite',default='evaluation/detailed-suite-v2.json');p.add_argument('--results',default='evaluation/runs/meddistract-detailed-v2');p.add_argument('--summary',default='evaluation/reports/detailed-ranking-v2-2026-10-29.json');p.add_argument('--publish',action='store_true');a=p.parse_args()
    if a.action=='init':initialize(a.suite)
    elif a.action=='run':run(a.suite,a.results,a.summary,a.publish)
    else:print(json.dumps(ranking(json.loads(Path(a.suite).read_text()),a.results),indent=2))
