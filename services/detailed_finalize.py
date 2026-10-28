"""One-off campaign completion receipts; never promotes a model or invents human data."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from services.api.ingest import file_sha256
from services.detailed_campaign import ranking
from services.detailed_diagnostics import run as diagnostics
from services.evidence_io import atomic_json


def process_alive(pid):
    if os.name!='nt':
        try:os.kill(pid,0);return True
        except ProcessLookupError:return False
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];kernel.GetExitCodeProcess.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return ctypes.get_last_error()==5
    try:
        code=wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise OSError('Cannot inspect owned campaign state')
        return code.value==259
    finally:kernel.CloseHandle(handle)


def draft_summary(path):
    report=json.loads(Path(path).read_text(encoding='utf-8'))
    if not report['complete']:raise ValueError('Draft screen still incomplete')
    truth={case['id']:sorted((f['section'],f['text'],(f['fact_id'],)) for f in case['facts']) for case in report['cases']}
    rows=[]
    for name,runs in [('deterministic',report['deterministic'])]+[(m['model'],m['runs']) for m in report['models']]:
        if len(runs)!=len(truth) or {r['id'] for r in runs}!=set(truth):raise ValueError('Missing/duplicate note screen cases')
        exact=failures=0
        for row in runs:
            failed=row.get('failed',False);failures+=failed
            actual=[] if failed else sorted((s['section'],s['text'],tuple(s['fact_ids'])) for s in row['output']['draft']['statements'])
            measured=not failed and actual==truth[row['id']]
            if row['exact_preservation']!=measured:raise ValueError('Saved preservation metric disagrees with actual statements')
            exact+=measured
        rows.append({'mode':name,'attempted_cases':len(runs),'exact_preservation_cases':exact,'failed_cases':failures})
    return {'report_sha256':file_sha256(path),'rows':rows,'clinical_note_accuracy_measured':False,'clinician_correction_time_measured':False,
        'limitation':'Exact preservation of upstream note fixture units is not independently adjudicated clinical note accuracy.'}


def finalize(publish=False):
    suite_path=Path('evaluation/detailed-suite-v2.json');suite=json.loads(suite_path.read_text())
    results=Path('evaluation/runs/meddistract-detailed-v2');summary=ranking(suite,results)
    root=Path('evaluation/reports');receipt_path=root/'detailed-campaign-execution-receipt-2026-10-29.json'
    if receipt_path.exists():raise FileExistsError('Preserve existing completion receipt')
    diagnostic_root=root/'detailed-diagnostics-final-v2';diagnostic_root.mkdir(exist_ok=True)
    completed=[]
    for report in results.glob('*.json'):
        data=json.loads(report.read_text(encoding='utf-8'))
        if not data.get('complete'):continue
        output=diagnostic_root/(report.stem+'.diagnostics.json')
        if not output.exists():
            cached=root/'detailed-diagnostics-v2'/output.name
            try:prior=json.loads(cached.read_text(encoding='utf-8'))
            except (OSError,json.JSONDecodeError):prior=None
            if prior and prior.get('report_sha256')==file_sha256(report):atomic_json(output,prior)
            else:diagnostics(suite['manifest'],report,output)
        completed.append({'candidate':data['candidate_id'],'mode':data['mode'],'clean':data['conditions']['clean'],'distracted':data['conditions']['distracted'],
            'report':report.as_posix(),'sha256':file_sha256(report),'diagnostics_sha256':file_sha256(output),'native_timestamp_bounds_valid':all(c['native_timestamp_bounds_valid'] for c in data['cases'])})
    notes=draft_summary(root/'detailed-drafting-2026-10-29.json')
    final_rank=root/'detailed-ranking-final-2026-10-29.json';atomic_json(final_rank,summary)
    lookup={j['candidate_id']:j for j in suite['jobs']};weights=set();finalists=[]
    for row in summary['ranked']:
        job=lookup[row['candidate_id']];weight=job.get('model_dir',job.get('profile_id'))
        if weight not in weights:weights.add(weight);finalists.append(row['candidate_id'])
        if len(finalists)==2:break
    expected={(cid,mode) for cid in finalists for mode in ['overlap','speech_aware']+(['context'] if lookup[cid]['runtime']=='whisper' else [])}
    receipt={'schema_version':'detailed_campaign_execution_receipt_v1','baseline_comparison_complete':summary['complete'],
        'required_finalist_ablations_complete':len(finalists)==2 and expected<={(r['candidate'],r['mode']) for r in completed},
        'suite_sha256':file_sha256(suite_path),'manifest_sha256':suite['manifest_sha256'],'ranked_candidates':len(summary['ranked']),
        'unranked_candidates':summary['unranked'],'completed_conditions':completed,'draft_preservation':notes,
        'maximum_normalized_wer':.05,'source_only_reviewer_packets_prepared':True,'independent_reviewers_available':False,
        'independent_annotation_complete':False,'clinician_study_observations_evaluated':0,'physical_hardware_validated':False,
        'real_patient_release_authorized':False,'paid_calls':0,'model_promoted':None}
    atomic_json(receipt_path,receipt)
    lines=['# Detailed campaign execution results','',f'All baseline comparisons complete: **{summary["complete"]}**. The 5% gate is unchanged. No model is promoted.','',
        '| Rank | Candidate | Clean WER | Distracted WER | Failed clean cases | Native timestamp bounds valid |','| --- | --- | --- | --- | --- | --- |']
    for r in summary['ranked']:lines.append(f'| {r["rank"]} | {r["candidate_id"]} | {r["clean"]["normalized_wer"]:.2%} | {r["distracted"]["normalized_wer"]:.2%} | {r["clean"]["failed_samples"]} | {r["native_timestamp_bounds_valid"]} |')
    lines+=['','Unranked or interrupted candidates remain in the JSON receipt; no WER is invented. See each native timestamp report and failure-inclusive condition summary.','',
        '## Completed chunking conditions','', '| Candidate | Mode | Clean WER | Distracted WER |','| --- | --- | --- | --- |']
    for r in completed:
        if r['mode']!='fixed':lines.append(f'| {r["candidate"]} | {r["mode"]} | {r["clean"]["normalized_wer"]:.2%} | {r["distracted"]["normalized_wer"]:.2%} |')
    lines+=['','## Reference-note preservation screen','', '| Mode | Exact cases | Failed cases |','| --- | --- | --- |']
    for r in notes['rows']:lines.append(f'| {r["mode"]} | {r["exact_preservation_cases"]}/{r["attempted_cases"]} | {r["failed_cases"]} |')
    lines+=['','This is preservation of supplied source-note fixture units, not clinical note accuracy or clinician correction time. Independent annotation, physical recording observations and institutional approval remain unperformed.','']
    markdown=root/'detailed-campaign-results-2026-10-29.md';markdown.write_text('\n'.join(lines),encoding='utf-8')
    if publish:
        paths=[p.as_posix() for p in results.glob('*.json')]+[p.as_posix() for p in diagnostic_root.glob('*.json')]+[str(receipt_path),str(final_rank),str(markdown),str(root/'detailed-drafting-2026-10-29.json')]
        subprocess.run(['git','add','--',*paths],check=True)
        subprocess.run(['git','commit','--only','-m','Publish detailed campaign results with all remaining validation gates','--',*paths],check=True)
        subprocess.run(['git','push','origin','main'],check=True)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--campaign-pid',type=int,required=True);p.add_argument('--publish',action='store_true');p.add_argument('--keep-awake',action='store_true');a=p.parse_args()
    if a.campaign_pid<=0:raise ValueError('Owned positive campaign PID required')
    power=None
    if a.keep_awake and os.name=='nt':
        import ctypes
        power=ctypes.WinDLL('kernel32').SetThreadExecutionState
        power.argtypes=[ctypes.c_uint32];power.restype=ctypes.c_uint32
        if not power(0x80000001):raise OSError('Cannot hold system-awake request for the owned campaign')
    try:
        deadline=time.monotonic()+72*3600
        while process_alive(a.campaign_pid):
            if time.monotonic()>=deadline:raise RuntimeError('Campaign remains active; no completion claimed')
            time.sleep(30)
        finalize(a.publish)
    finally:
        if power:power(0x80000000)
