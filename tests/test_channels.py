"""Multichannel transport, isolation, overlap and all-or-nothing worker publishing."""
import io
import wave
from pathlib import Path

import pytest

from services.api.ingest import inspect_pcm_wav, run_once as ingest_once, InvalidAudio
from services.asr.adapter import ASRFailure
from services.asr.worker import run_once
from tests.test_foundation import headers, queue_upload
from tests.test_transcription import environment, SyntheticAdapter


def recording(count, rate=16000):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as audio:
        audio.setparams((count, 2, rate, 0, 'NONE', 'not compressed'))
        audio.writeframes(b''.join((index+1).to_bytes(2, 'little') for index in range(count)) * (rate//10))
    return buffer.getvalue()


def queued(env, count):
    eid, upload, _, ingest = queue_upload(env.client, recording(count))
    assert ingest_once(env.path, env.assets)['status'] == 'succeeded'
    job = env.client.post(f'/v1/encounters/{eid}/transcriptions', headers=headers(), json={
        'audio_asset_id':upload['id'], 'inference_profile_id':env.profile.profile_id})
    assert job.status_code == 202, job.text
    return eid, upload


@pytest.mark.parametrize('count', [2, 3, 8])
def test_isolated_channels_overlap_and_scoped_playback(environment, count):
    env=environment
    eid, upload=queued(env, count)
    seen=[]
    class Adapter(SyntheticAdapter):
        def transcribe(self, source, metadata, checkpoint):
            with wave.open(str(source), 'rb') as audio:
                assert audio.getnchannels()==1
                value=int.from_bytes(audio.readframes(1), 'little')
                assert audio.readframes(1600)==value.to_bytes(2,'little')*1599
            seen.append(value)
            return super().transcribe(source, metadata, checkpoint)
    assert run_once(env.path, env.assets, Adapter)['status']=='succeeded'
    assert seen==list(range(1,count+1))
    tx=env.client.get(f'/v1/encounters/{eid}/workspace', headers=headers()).json()['transcript']
    assert len(tx['channels'])==count
    assert [s['channel_index'] for s in tx['segments']]==list(range(count))
    assert all(s['start_ms']==0 and s['end_ms']==80 and s['role']=='unknown' and s['role_status']=='unconfirmed' for s in tx['segments'])
    assert {g['channel_index'] for g in tx['untranscribed_intervals']}==set(range(count))
    route=f"/v1/encounters/{eid}/audio/{upload['id']}?channel={count-1}"
    response=env.client.get(route, headers=headers())
    assert response.status_code==200
    with wave.open(io.BytesIO(response.content),'rb') as audio:
        assert audio.getnchannels()==1
        assert audio.readframes(1600)==count.to_bytes(2,'little')*1600
    assert env.client.get(route, headers=headers('b'*40)).status_code==404
    assert env.client.get(f"/v1/encounters/{eid}/audio/{upload['id']}?channel={count}",headers=headers()).status_code==422
    # A source correction retains channel identity and makes a new immutable version.
    body={'segments':[{'segment_id':s['segment_id'],'text':s['text'],'role':'interpreter' if s['channel_index']==count-1 else 'unknown'} for s in tx['segments']],
          'english_confirmed':True,'source_completeness_reviewed':False,'source_review_reason':'Review pending','correction_reason':'Confirm interpreter channel'}
    edited=env.client.patch(f"/v1/encounters/{eid}/transcripts/{tx['id']}",headers={**headers(),'If-Match':f'"{tx["sha256"]}"'},json=body)
    assert edited.status_code==201, edited.text
    assert edited.json()['segments'][-1]['channel_index']==count-1
    assert edited.json()['segments'][-1]['role']=='interpreter'


def test_failed_channel_never_publishes_partial_transcript(environment):
    env=environment
    eid,_=queued(env,3)
    class Broken(SyntheticAdapter):
        def transcribe(self, source, metadata, checkpoint):
            with wave.open(str(source),'rb') as audio:
                if audio.readframes(1)==b'\x02\x00':
                    raise ASRFailure('asr_failed')
            return super().transcribe(source, metadata, checkpoint)
    assert run_once(env.path,env.assets,Broken)['status']=='failed'
    assert env.client.get(f'/v1/encounters/{eid}/workspace',headers=headers()).json()['transcript'] is None


def test_ninth_channel_rejected(tmp_path):
    source=tmp_path/'nine.wav';source.write_bytes(recording(9))
    with pytest.raises(InvalidAudio):inspect_pcm_wav(source)


def test_decoder_preserves_three_distinct_channels(tmp_path):
    pytest.importorskip('av')
    from services.media_decoder import normalize
    source=tmp_path/'three.wav';target=tmp_path/'normalized.wav'
    source.write_bytes(recording(3,48000))
    assert normalize(source,target,'audio/wav')['error_code'] is None
    assert inspect_pcm_wav(target)['channels']==3
    with wave.open(str(target),'rb') as audio:
        import numpy as np
        values=np.frombuffer(audio.readframes(1600),dtype='<i2').reshape(-1,3)
        assert (values[100:]==[1,2,3]).all()
