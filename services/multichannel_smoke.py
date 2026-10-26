"""Real local worker smoke using three padded public clips, not a consultation."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
from uuid import uuid4
import wave
import httpx
import numpy as np
from services.api.ingest import file_sha256
from services.evaluation import score


def run(output):
    output=Path(output)
    if output.exists():raise ValueError('Preserve previous evidence')
    root=Path('evaluation/datasets/primock57-smoke-v1')
    manifest=json.loads((root/'manifest.json').read_text())
    if file_sha256(root/'manifest.json')!=json.loads((root/'lock.json').read_text())['manifest_sha256']:
        raise ValueError('Frozen manifest changed')
    sources=manifest['samples'][:3];signals=[]
    for sample in sources:
        source=root/sample['audio']
        if file_sha256(source)!=sample['audio_sha256']:raise ValueError('Source changed')
        with wave.open(str(source),'rb') as audio:
            if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())!=(1,2,16000):raise ValueError('Invalid source profile')
            signals.append(np.frombuffer(audio.readframes(audio.getnframes()),dtype='<i2'))
    frames=max(map(len,signals))
    content=np.stack([np.pad(s,(0,frames-len(s))) for s in signals],axis=1).astype('<i2').tobytes()
    target=Path('data/multichannel-smoke.wav')
    with wave.open(str(target),'wb') as audio:
        audio.setparams((3,2,16000,0,'NONE','not compressed'));audio.writeframes(content)
    result={'schema_version':'multichannel_real_worker_smoke_v1','scope':'three_padded_public_clips_shared_origin_not_a_consultation',
        'source_manifest_sha256':file_sha256(root/'manifest.json'),'source_attribution':manifest['attribution'],
        'input_sha256':file_sha256(target),'channels':3,'frames':frames,'clinical_acceptance':False,
        'complete':False,'failed':False,'runs':[]}
    started=time.perf_counter()
    config=json.loads(Path('data/local-config.json').read_text())
    try:
        with httpx.Client(base_url='http://127.0.0.1:8003',headers={'Authorization':'Bearer '+config['access_key']},timeout=60,trust_env=False) as client:
            def request(method,path,**kwargs):
                response=client.request(method,path,**kwargs)
                if not response.is_success:raise ValueError('http_status_'+str(response.status_code))
                return response.json()
            def wait(path):
                deadline=time.monotonic()+600
                while time.monotonic()<deadline:
                    job=request('GET',path)
                    if job['status']=='succeeded':return job
                    if job['status'] in ('failed','cancelled'):raise ValueError('job_'+job['status'])
                    time.sleep(1)
                raise ValueError('job_deadline_exceeded')
            profile=request('GET','/v1/session')['asr_profiles'][0];result['profile_id']=profile
            eid=request('POST','/v1/encounters',headers={'Idempotency-Key':str(uuid4())},json={
                'patient_reference_id':str(uuid4()),'patient_identifiers_confirmed':True,'synthetic_data':True})['id']
            base=f'/v1/encounters/{eid}'
            request('POST',base+'/authorizations',json={'scopes':['recording','local_processing'],'policy_version':'public-channel-smoke-v1',
                'method':'written','expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()})
            upload=request('POST',base+'/audio-uploads',headers={'Idempotency-Key':str(uuid4())},json={
                'bytes':target.stat().st_size,'sha256':file_sha256(target),'media_type':'audio/wav'})
            request('PUT',upload['content_url'],content=target.read_bytes(),headers={'Content-Type':'audio/wav'})
            wait(request('POST',base+f"/audio-uploads/{upload['id']}/complete")['status_url'])
            wait(request('POST',base+'/transcriptions',headers={'Idempotency-Key':str(uuid4())},json={
                'audio_asset_id':upload['id'],'inference_profile_id':profile})['status_url'])
            workspace=request('GET',base+'/workspace');tx=workspace['transcript']
            result['transcript_sha256']=tx['sha256'];result['duration_ms']=tx['duration_ms']
            result['channel_provenance']=tx['channels']
            result['timestamps_valid']=all(0<=s['start_ms']<s['end_ms']<=tx['duration_ms'] for s in tx['segments'])
            result['roles_unconfirmed']=all(s['role']=='unknown' and s['role_status']=='unconfirmed' for s in tx['segments'])
            result['no_automatic_note_or_approval']=workspace['note'] is None and workspace['approval'] is None
            for index,sample in enumerate(sources):
                hypothesis=' '.join(s['text'] for s in tx['segments'] if s['channel_index']==index)
                result['runs'].append({'channel_index':index,'source_sample':sample['sample_id'],'source_audio_sha256':sample['audio_sha256'],
                    'reference':sample['reference'],'hypothesis':hypothesis,'score':score(sample['reference'],hypothesis)})
            result['complete']=True
    except Exception as exc:
        result['failed']=True;result['error_type']=type(exc).__name__
        # Preserve every reference and denominator on operational failure.
        result['runs']=[{'channel_index':i,'reference':s['reference'],'hypothesis':'','score':score(s['reference'],'')} for i,s in enumerate(sources)]
    result['wall_seconds']=time.perf_counter()-started
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    result=run(args.output);print(json.dumps({k:result.get(k) for k in ('complete','failed','timestamps_valid','roles_unconfirmed','no_automatic_note_or_approval')}))
    raise SystemExit(1 if result['failed'] else 0)
