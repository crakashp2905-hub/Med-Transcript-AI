"""Real-worker long-duration stress fixture; repeated speech is not clinical acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4
import wave
import httpx
from services.api.ingest import file_sha256
from services.evaluation import score


def run(output):
    if Path(output).exists():raise ValueError('Preserve previous evidence')
    source=Path('evaluation/datasets/primock57-smoke-v1/day1_consultation01_patient.utterance03.wav')
    manifest_path=source.parent/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    if file_sha256(manifest_path)!=json.loads((source.parent/'lock.json').read_text())['manifest_sha256']:
        raise ValueError('Frozen source manifest changed')
    sample=next(s for s in manifest['samples'] if Path(s['audio']).name==source.name)
    if file_sha256(source)!=sample['audio_sha256']:raise ValueError('Source audio changed')
    with wave.open(str(source),'rb') as audio:
        if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())!=(1,2,16000):raise ValueError('Source must be mono PCM16 16kHz')
        pcm=audio.readframes(audio.getnframes())
    if len(pcm)>60*32000:raise ValueError('Source does not fit stress tile')
    tile=pcm+b'\0'*(60*32000-len(pcm))
    config=json.loads(Path('data/local-config.json').read_text())
    result={'schema_version':'real_worker_long_duration_stress_v1',
            'scope':'synthetic_repeated_public_clip_transport_and_timestamp_stress_not_a_clinical_consultation',
            'source_clip_sha256':file_sha256(source),'source_manifest_sha256':file_sha256(manifest_path),
            'source_attribution':manifest.get('attribution','PriMock57 CC-BY-4.0; see source dataset attribution'),
            'tile_seconds':60,'clinical_acceptance':False,'complete':False,'runs':[],
            'limitations':['Repeated speech and long digital silence are not representative consultation accuracy.',
                          'Concurrent local benchmark load affects latency; no performance target is inferred.',
                          'Application development ASR is not qualified under the 5% acceptance gate.']}
    root=Path('data/long-recording-stress');root.mkdir(exist_ok=True)
    with httpx.Client(base_url='http://127.0.0.1:8003',headers={'Authorization':'Bearer '+config['access_key']},
                      timeout=60,trust_env=False,follow_redirects=False) as client:
        def request(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            if not response.is_success:raise ValueError(f'http_status_{response.status_code}')
            return response.json()
        profiles=request('GET','/v1/session')['asr_profiles']
        if not profiles:raise ValueError('No development ASR configured')
        def wait(path):
            deadline=time.monotonic()+1800
            while time.monotonic()<deadline:
                job=request('GET',path)
                if job['status']=='succeeded':return job
                if job['status'] in ('failed','cancelled'):raise ValueError('job_'+job['status'])
                time.sleep(2)
            raise ValueError('job_deadline_exceeded')
        for minutes in (20,30):
            file=root/f'public-repeated-{minutes}min.wav'
            with wave.open(str(file),'wb') as out:
                out.setparams((1,2,16000,0,'NONE','not compressed'))
                for _ in range(minutes):out.writeframesraw(tile)
            reference=' '.join([sample['reference']]*minutes)
            row={'minutes':minutes,'input_sha256':file_sha256(file),'failed':False,'reference':reference}
            started=time.perf_counter()
            try:
                encounter=request('POST','/v1/encounters',headers={'Idempotency-Key':str(uuid4())},json={
                    'patient_reference_id':str(uuid4()),'patient_identifiers_confirmed':True,'synthetic_data':True})
                eid=encounter['id'];row['encounter_id']=eid;base=f'/v1/encounters/{eid}'
                from datetime import datetime,timedelta,timezone
                request('POST',base+'/authorizations',json={'scopes':['recording','local_processing'],
                    'policy_version':'public-repeated-stress-v1','method':'written',
                    'expires_at':(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()})
                upload=request('POST',base+'/audio-uploads',headers={'Idempotency-Key':str(uuid4())},json={
                    'bytes':file.stat().st_size,'sha256':row['input_sha256'],'media_type':'audio/wav'})
                request('PUT',upload['content_url'],headers={'Content-Type':'audio/wav'},content=file.read_bytes())
                ingest=request('POST',base+f'/audio-uploads/{upload["id"]}/complete');wait(ingest['status_url'])
                job=request('POST',base+'/transcriptions',headers={'Idempotency-Key':str(uuid4())},json={
                    'audio_asset_id':upload['id'],'inference_profile_id':profiles[0]});finished=wait(job['status_url'])
                workspace=request('GET',base+'/workspace');tx=workspace['transcript']
                valid=tx['duration_ms']==minutes*60000 and tx['input_sha256']==row['input_sha256']
                valid &= all(0<=s['start_ms']<s['end_ms']<=tx['duration_ms'] for s in tx['segments'])
                valid &= all(a['start_ms']<=b['start_ms'] for a,b in zip(tx['segments'],tx['segments'][1:]))
                if not valid:raise ValueError('invalid_source_timeline')
                hypothesis=' '.join(s['text'] for s in tx['segments'])
                row.update(transcript=tx,job=finished,reference=reference,hypothesis=hypothesis,
                           timestamp_bounds_valid=True,source_audio_duration_preserved=True,
                           note_created=workspace['note'] is not None,approval_created=workspace['approval'] is not None,
                           **score(reference,hypothesis))
                if row['note_created'] or row['approval_created']:raise ValueError('unexpected_automatic_note_or_approval')
            except (ValueError,httpx.HTTPError) as exc:
                row.update(failed=True,failure_code=str(exc) if isinstance(exc,ValueError) else 'local_transport_failure',
                           scored_hypothesis='',**score(reference,''))
            row['wall_seconds']=time.perf_counter()-started;result['runs'].append(row)
            Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(minutes,'minutes failed=',row['failed'],flush=True)
    result['complete']=True
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);a=p.parse_args()
    result=run(a.out)
    if any(r['failed'] for r in result['runs']):raise SystemExit(1)
