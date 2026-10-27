import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from services.api.storage import Store
from services.asr.worker import run_once
from tests.test_foundation import setup, headers, create, upload_session, wav_bytes
from tests.test_transcription import environment, SyntheticAdapter
from tests.test_channels import queued
from services.asr.adapter import ASRFailure


def append(client,url,content,offset,token=None):
    return client.patch(url,content=content,headers={**headers(token or 'a'*40),'Content-Type':'audio/wav',
        'Upload-Offset':str(offset),'Upload-Chunk-SHA256':hashlib.sha256(content).hexdigest()})


def test_upload_resumes_and_replays_identical_chunk_without_duplication(setup):
    client,db,_=setup;eid=create(client);content=wav_bytes()
    upload,_=upload_session(client,eid,content);url=upload['content_url']
    first=content[:70]
    assert append(client,url,first,0).json()['received_bytes']==70
    assert append(client,url,first,0).json()['received_bytes']==70
    assert append(client,url,b'wrong',0).status_code==409
    assert append(client,url,content[70:],71).status_code==409
    assert append(client,url,content[70:],70,'b'*40).status_code==404
    state=client.get(f'/v1/encounters/{eid}/audio-uploads/{upload["id"]}',headers=headers()).json()
    assert state['received_bytes']==70
    # Simulate a write that reached disk but whose offset transaction never committed.
    partial=Path(db).parent/'assets'/f'{upload["id"]}.resume.part'
    with partial.open('ab') as output:output.write(b'uncommitted tail')
    response=append(client,url,content[70:],70)
    assert response.status_code==200 and response.json()['status']=='uploaded'
    assert append(client,url,content[70:],70).status_code==200
    assert (partial.parent/f'{upload["id"]}.wav').read_bytes()==content
    complete=client.post(f'/v1/encounters/{eid}/audio-uploads/{upload["id"]}/complete',headers=headers())
    assert complete.status_code==202


def test_bad_chunk_does_not_advance_offset_or_create_asset(setup):
    client,db,_=setup;eid=create(client);content=wav_bytes();upload,_=upload_session(client,eid,content)
    response=client.patch(upload['content_url'],content=content[:50],headers={**headers(),'Content-Type':'audio/wav','Upload-Offset':'0','Upload-Chunk-SHA256':'0'*64})
    assert response.status_code==422
    state=client.get(f'/v1/encounters/{eid}/audio-uploads/{upload["id"]}',headers=headers()).json()
    assert state['received_bytes']==0


def test_channel_retry_uses_verified_completed_channels_and_retains_failed_attempt(environment):
    env=environment;eid,upload=queued(env,3);seen=[]
    class Flaky(SyntheticAdapter):
        def transcribe(self,source,metadata,checkpoint):
            import wave
            with wave.open(str(source),'rb') as audio:value=int.from_bytes(audio.readframes(1),'little')
            seen.append(value)
            if seen==[1,2]:raise ASRFailure('asr_failed')
            return super().transcribe(source,metadata,checkpoint)
    first=run_once(env.path,env.assets,Flaky)
    assert first['status']=='failed'
    with Store(env.path).transaction() as con:
        assert con.execute('SELECT count(*) FROM asr_checkpoints').fetchone()[0]==1
    assert env.client.post(f'/v1/jobs/{first["id"]}/retry',headers=headers('b'*40)).status_code==404
    assert env.client.post(f'/v1/jobs/{first["id"]}/retry',headers=headers()).status_code==202
    assert run_once(env.path,env.assets,Flaky)['status']=='succeeded'
    assert seen==[1,2,2,3]
    with Store(env.path).transaction() as con:
        attempts=con.execute('SELECT status,error_code FROM job_attempts ORDER BY attempt').fetchall()
        assert [(r['status'],r['error_code']) for r in attempts]==[('failed','asr_failed'),('succeeded',None)]
    assert env.client.get(f'/v1/encounters/{eid}/workspace',headers=headers()).json()['note'] is None


def test_changed_checkpoint_is_rejected(environment):
    env=environment;eid,_=queued(env,3)
    class Broken(SyntheticAdapter):
        calls=0
        def transcribe(self,*args):
            self.calls+=1
            if self.calls==2:raise ASRFailure('asr_failed')
            return super().transcribe(*args)
    first=run_once(env.path,env.assets,Broken)
    with Store(env.path).transaction() as con:con.execute("UPDATE asr_checkpoints SET body='{}'")
    assert env.client.post(f'/v1/jobs/{first["id"]}/retry',headers=headers()).status_code==202
    assert run_once(env.path,env.assets,SyntheticAdapter)['status']=='failed'
    with Store(env.path).transaction() as con:
        assert con.execute('SELECT error_code FROM jobs WHERE id=?',(first['id'],)).fetchone()[0]=='asset_integrity_failure'


def test_live_preview_never_becomes_a_saved_source_or_note(environment):
    env=environment;eid,upload,_,_=__import__('tests.test_foundation',fromlist=['queue_upload']).queue_upload(env.client)
    from services.api.ingest import run_once as ingest_once
    assert ingest_once(env.path,env.assets)['status']=='succeeded'
    body={'audio_asset_id':upload['id'],'inference_profile_id':env.profile.profile_id,'preview_only':True,'timeline_offset_ms':15000}
    response=env.client.post(f'/v1/encounters/{eid}/transcriptions',headers=headers(),json=body)
    assert response.status_code==202,response.text
    assert run_once(env.path,env.assets,SyntheticAdapter)['status']=='succeeded'
    job=env.client.get(response.json()['status_url'],headers=headers()).json()
    assert job['result']['approvable'] is False
    assert job['result']['provisional_segments'][0]['start_ms']==15000
    workspace=env.client.get(f'/v1/encounters/{eid}/workspace',headers=headers()).json()
    assert workspace['transcript'] is None and workspace['note'] is None and workspace['approval'] is None
    body['preview_only']=False;body['timeline_offset_ms']=0
    assert env.client.post(f'/v1/encounters/{eid}/transcriptions',headers=headers(),json=body).status_code==409
    from services.maintenance import expire_previews
    with Store(env.path).transaction() as con:
        con.execute("UPDATE jobs SET updated_at='2020-01-01T00:00:00+00:00' WHERE id=?",(job['id'],))
    assert expire_previews(env.path,env.assets)['expired_preview_caches']==1
    assert not (Path(env.assets)/f'{upload["id"]}.wav').exists()
    with Store(env.path).transaction() as con:
        assert con.execute('SELECT count(*) FROM job_attempts').fetchone()[0]==1


def test_model_cache_reuses_weights_but_still_checks_artifact_integrity(environment,monkeypatch):
    pytest.importorskip('numpy')
    import sys
    from types import SimpleNamespace
    from services.asr.adapter import FasterWhisperAdapter,loaded_model
    loaded_model.cache_clear();calls=[]
    class Model:
        def __init__(self,*args,**kwargs):calls.append('loaded')
        def transcribe(self,*args,**kwargs):return iter([SimpleNamespace(start=0.0,end=0.08,text=' synthetic')]),SimpleNamespace(duration=.1)
    monkeypatch.setitem(sys.modules,'faster_whisper',SimpleNamespace(WhisperModel=Model))
    monkeypatch.setattr('services.asr.adapter.importlib.metadata.version',lambda name:'1.2.1')
    source=Path(environment.assets)/'signal.wav';source.parent.mkdir(exist_ok=True)
    content=bytearray(wav_bytes());content[-2:]=b'\x01\x00';source.write_bytes(content)
    adapter=FasterWhisperAdapter(environment.profile);metadata={'channels':1,'sample_rate':16000,'frames':1600}
    try:
        adapter.transcribe(source,metadata,lambda:None);adapter.transcribe(source,metadata,lambda:None)
        assert calls==['loaded']
        (Path(environment.profile.model_dir)/'tokenizer.json').write_bytes(b'changed')
        with pytest.raises(ASRFailure):adapter.transcribe(source,metadata,lambda:None)
    finally:loaded_model.cache_clear()


def test_additive_preview_migration_preserves_resumable_upload_offsets(tmp_path):
    import sqlite3
    from services.api.storage import MIGRATIONS
    path=str(tmp_path/'old.sqlite3')
    with sqlite3.connect(path) as con:
        for version,migration in enumerate(MIGRATIONS[:9],1):con.executescript(migration);con.execute(f'PRAGMA user_version={version}')
        eid=str(uuid4());uid=str(uuid4())
        con.execute('INSERT INTO encounters (id,tenant,clinician,body,created_at) VALUES (?,?,?,?,?)',(eid,'tenant','clinician','{}','2026-10-27'))
        con.execute("INSERT INTO uploads (id,encounter,expected_bytes,expected_sha256,status,created_at,expires_at,received_bytes) VALUES (?,?,100,?,'open',?,?,70)",(uid,eid,'a'*64,'2026-10-27','2026-10-28'))
    with Store(path).transaction() as con:
        assert con.execute('SELECT received_bytes FROM uploads').fetchone()[0]==70
        assert {'preview_only','timeline_offset_ms','preview_cache_expired'}<={r['name'] for r in con.execute('PRAGMA table_info(jobs)')}


def test_reserved_audio_is_rejected_for_development_before_download(tmp_path,monkeypatch):
    import services.prepare_full_consultations as preparation
    def blocked(*args):raise AssertionError('Network should not be reached')
    monkeypatch.setattr(preparation,'download',blocked)
    with pytest.raises(ValueError,match='Reserved acceptance'):
        preparation.prepare(tmp_path/'corpus',['day5_consultation05'])


def test_fast_audio_copy_throttles_lease_writes_but_force_checks_revocation(environment,monkeypatch):
    from services.asr.worker import Lease
    from datetime import datetime,timedelta,timezone
    env=environment;eid,_=queued(env,2)
    with Store(env.path).transaction() as con:
        job=con.execute("SELECT id FROM jobs WHERE stage='transcription'").fetchone()[0]
        con.execute("UPDATE jobs SET status='running',lease_token='test-token',lease_expires_at=? WHERE id=?",((datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),job))
    monkeypatch.setattr('services.asr.worker.time.monotonic',lambda:100.0)
    lease=Lease(Store(env.path),job,'test-token',eid)
    for _ in range(1000):lease.checkpoint()
    assert lease.db_checkpoints==1 and lease.checkpoint_calls==1000
    with Store(env.path).transaction() as con:con.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(job,))
    with pytest.raises(ASRFailure):lease.checkpoint(force=True)
