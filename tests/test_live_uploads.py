import hashlib
import io
import wave

from tests.test_foundation import setup, create, headers, authorization, wav_bytes
from tests.test_recovery import append


def stream(client, eid):
    route=f'/v1/encounters/{eid}'
    client.post(route+'/authorizations',headers=headers(),json=authorization())
    response=client.post(route+'/stream-uploads',headers=headers(),json={'format':'pcm','channels':1,'media_type':'audio/wav'})
    assert response.status_code==201,response.text
    return route,response.json()


def test_live_prefix_requires_sealing_and_recovers_valid_wav(setup):
    client,_,_=setup;eid=create(client);route,item=stream(client,eid);raw=wav_bytes()[44:]
    assert append(client,item['content_url'],raw,44).json()['received_bytes']==len(raw)+44
    assert client.post(route+f'/audio-uploads/{item["id"]}/complete',headers=headers()).status_code==409
    recovery=client.get(route+f'/stream-uploads/{item["id"]}/recovery',headers=headers())
    assert recovery.status_code==200
    with wave.open(io.BytesIO(recovery.content)) as audio:
        assert audio.getnframes()==len(raw)//2
        assert audio.readframes(audio.getnframes())==raw
    body={'bytes':len(recovery.content),'sha256':hashlib.sha256(recovery.content).hexdigest()}
    sealed=client.post(route+f'/stream-uploads/{item["id"]}/seal',headers=headers(),json=body)
    assert sealed.status_code==200,sealed.text
    assert client.post(route+f'/stream-uploads/{item["id"]}/seal',headers=headers(),json=body).status_code==200
    assert client.post(route+f'/audio-uploads/{item["id"]}/complete',headers=headers()).status_code==202
    assert client.get(route+'/workspace',headers=headers()).json()['transcript'] is None


def test_live_seal_integrity_scope_and_withdrawal_fail_closed(setup):
    client,_,_=setup;eid=create(client);route,item=stream(client,eid);raw=wav_bytes()[44:]
    append(client,item['content_url'],raw,44)
    url=route+f'/stream-uploads/{item["id"]}/seal';body={'bytes':len(raw)+44,'sha256':'0'*64}
    assert client.post(url,headers=headers('b'*40),json=body).status_code==404
    assert client.post(url,headers=headers(),json=body).status_code==422
    assert client.get(route+f'/audio-uploads/{item["id"]}',headers=headers()).json()['status']=='open'
    from services.api.storage import Store
    with Store(setup[1]).transaction() as con:
        con.execute("UPDATE authorizations SET withdrawn_at='2026-01-01T00:00:00+00:00'")
    assert client.post(url,headers=headers(),json=body).status_code==403
    assert append(client,item['content_url'],raw,len(raw)+44).status_code==403


def test_backup_includes_only_committed_live_prefix_and_seal_recovers_rename(setup,tmp_path):
    from pathlib import Path
    from services.maintenance import backup,restore
    client,db,_=setup;eid=create(client);route,item=stream(client,eid);raw=wav_bytes()[44:]
    append(client,item['content_url'],raw,44)
    partial=Path(db).parent/'assets'/f'{item["id"]}.resume.part'
    with partial.open('ab') as output:output.write(b'uncommitted')
    snapshot=tmp_path/'snapshot';backup(db,partial.parent,snapshot)
    saved=snapshot/'assets'/partial.name
    assert saved.stat().st_size==44+len(raw)
    restored=tmp_path/'restored';restore(snapshot,restored,db)
    assert (restored/'assets'/partial.name).read_bytes()==saved.read_bytes()
    # Crash between the source rename and SQL commit: retry must seal the
    # original prefix without permitting an altered source.
    recovery=client.get(route+f'/stream-uploads/{item["id"]}/recovery',headers=headers()).content
    destination=partial.with_name(f'{item["id"]}.wav');destination.write_bytes(recovery);partial.unlink()
    body={'bytes':len(recovery),'sha256':hashlib.sha256(recovery).hexdigest()}
    assert client.post(route+f'/stream-uploads/{item["id"]}/seal',headers=headers(),json=body).status_code==200
