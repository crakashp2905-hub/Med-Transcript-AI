"""Observe an existing isolated synthetic job; never alters job or approval state."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from uuid import UUID
import httpx


def observe(interruption,original,output):
    destination=Path(output)
    if destination.exists():raise ValueError('Preserve previous evidence')
    receipt=json.loads(Path(interruption).read_text());prior=json.loads(Path(original).read_text())
    if receipt['original_report_sha256']!=hashlib.sha256(Path(original).read_bytes()).hexdigest():raise ValueError('Original report changed')
    job_id=str(UUID(receipt['running_jobs_at_worker_stop'][0]['id']))
    config=json.loads(Path('data/local-config.json').read_text())
    result={'schema_version':'isolated_recovered_job_v1','interruption_sha256':hashlib.sha256(Path(interruption).read_bytes()).hexdigest(),
        'original_report_sha256':hashlib.sha256(Path(original).read_bytes()).hexdigest(),'job_id':job_id,
        'clinical_acceptance':False,'complete':False,'failed':False}
    started=time.perf_counter();previous=-1
    with httpx.Client(base_url='http://127.0.0.1:8003',headers={'Authorization':'Bearer '+config['access_key']},timeout=60,trust_env=False) as client:
        def get(path):
            response=client.get(path);response.raise_for_status();return response.json()
        try:
            deadline=time.monotonic()+1800
            while time.monotonic()<deadline:
                job=get(f'/v1/jobs/{job_id}');result['job']=job
                count=(job.get('progress') or {}).get('completed_channels',-1)
                if count!=previous:print('recovered completed channels:',count,flush=True);previous=count
                if job['status'] in ('failed','cancelled'):raise ValueError('recovered_job_'+job['status'])
                if job['status']=='succeeded':break
                time.sleep(2)
            else:raise ValueError('recovery_observation_timeout')
            eid=job['encounter_id'];tid=job['result']['transcript_version_id']
            tx=get(f'/v1/encounters/{eid}/transcripts/{tid}');workspace=get(f'/v1/encounters/{eid}/workspace')
            result.update(duration_ms=tx['duration_ms'],channels=len(tx.get('channels',[])),
                input_sha256=tx['input_sha256'],source_input_matches_original=tx['input_sha256']==prior['runs'][0]['input_sha256'],
                timestamp_bounds_valid=all(0<=s['start_ms']<s['end_ms']<=tx['duration_ms'] for s in tx['segments']),
                roles_unconfirmed=all(s['role']=='unknown' and s['role_status']=='unconfirmed' for s in tx['segments']),
                no_automatic_note_or_approval=workspace['note'] is None and workspace['approval'] is None,
                worker_timing=tx['provenance'].get('worker_timing'),channel_provenance=tx.get('channels',[]),transcript_sha256=tx['sha256'])
            if not all(result[k] for k in ('source_input_matches_original','timestamp_bounds_valid','roles_unconfirmed','no_automatic_note_or_approval')):raise ValueError('recovery_invariant_failed')
            result['complete']=True
        except (ValueError,httpx.HTTPError) as error:
            result['failed']=True;result['error_type']=type(error).__name__
    result['observation_wall_seconds']=time.perf_counter()-started
    destination.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result.get(k) for k in ('complete','failed','channels','duration_ms')}))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--interruption',required=True);p.add_argument('--original',required=True);p.add_argument('--out',required=True);a=p.parse_args();r=observe(a.interruption,a.original,a.out);raise SystemExit(1 if r['failed'] else 0)
