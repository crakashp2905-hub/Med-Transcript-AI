"""Durable live byte prefixes. Only a sealed, hash-verified source can be ingested."""
from datetime import datetime,timedelta,timezone
import os
import struct
from typing import Literal
from uuid import UUID,uuid4
from fastapi import Depends,Header,HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,ConfigDict,Field
from services.api.ingest import MAX_UPLOAD_BYTES,file_sha256


class StreamInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    format:Literal['pcm','media']
    channels:int=Field(ge=1,le=8,strict=True)
    media_type:Literal['audio/wav','audio/webm','audio/ogg','audio/mp4']


class SealInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    bytes:int=Field(ge=1,le=MAX_UPLOAD_BYTES,strict=True)
    sha256:str=Field(pattern='^[a-f0-9]{64}$')


def header(size,channels):
    return struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',36+size,b'WAVE',b'fmt ',16,1,channels,16000,32000*channels,channels*2,16,b'data',size)


def register(app,database,identity,encounter,upload_row,require_processing,require_live_upload,assets,audit,replay,remember):
    @app.post('/v1/encounters/{eid}/stream-uploads',status_code=201)
    def create(eid:UUID,body:StreamInput,idempotency_key:str=Header(alias='Idempotency-Key',min_length=8,max_length=128,pattern='^[a-zA-Z0-9_.-]+$'),actor=Depends(identity)):
        if body.format=='pcm' and body.media_type!='audio/wav':raise HTTPException(422,'pcm_stream_requires_wav')
        if body.format=='media' and body.media_type=='audio/wav':raise HTTPException(422,'wav_stream_requires_pcm')
        stamp=datetime.now(timezone.utc);uid=str(uuid4());partial=assets/f'{uid}.resume.part'
        try:
            with database() as con:
                encounter(con,eid,actor);require_processing(con,eid)
                scope,fingerprint,previous=replay(con,actor,f'stream-upload:{eid}',idempotency_key,body.model_dump())
                if previous:return previous
                received=44 if body.format=='pcm' else 0
                with partial.open('xb') as output:
                    if received:output.write(header(0,body.channels))
                    output.flush();os.fsync(output.fileno())
                expires=(stamp+timedelta(hours=2)).isoformat()
                con.execute("INSERT INTO uploads (id,encounter,expected_bytes,expected_sha256,status,created_at,expires_at,media_type,received_bytes,stream_format,stream_channels) VALUES (?,?,?,?,'open',?,?,?,?,?,?)",
                    (uid,str(eid),MAX_UPLOAD_BYTES,'0'*64,stamp.isoformat(),expires,body.media_type,received,body.format,body.channels))
                result={'id':uid,'status':'open','received_bytes':received,'expires_at':expires,'content_url':f'/v1/encounters/{eid}/audio-uploads/{uid}/content'}
                remember(con,scope,fingerprint,result);audit(con,actor,'live_upload_created',uid)
            return result
        except BaseException:
            partial.unlink(missing_ok=True)
            raise

    @app.post('/v1/encounters/{eid}/stream-uploads/{uid}/seal')
    def seal(eid:UUID,uid:UUID,body:SealInput,actor=Depends(identity)):
        stamp=datetime.now(timezone.utc);token=str(uuid4())
        partial=assets/f'{uid}.resume.part';destination=assets/f'{uid}.wav'
        with database() as con:
            row=upload_row(con,eid,uid,actor);require_processing(con,eid)
            if not row['stream_format']:raise HTTPException(409,'not_a_live_upload')
            if row['stream_sealed']:
                if row['expected_bytes']!=body.bytes or row['expected_sha256']!=body.sha256:raise HTTPException(409,'sealed_source_changed')
                return {'id':str(uid),'status':row['status'],'received_bytes':body.bytes}
            require_live_upload(row)
            if row['received_bytes']!=body.bytes:raise HTTPException(409,'live_upload_incomplete')
            if row['status']=='uploading' and row['stream_seal_expires_at'] and datetime.fromisoformat(row['stream_seal_expires_at'])>stamp:
                raise HTTPException(409,'live_upload_sealing')
            if row['status'] not in ('open','uploading'):raise HTTPException(409,'upload_not_open')
            con.execute("UPDATE uploads SET status='uploading',stream_seal_token=?,stream_seal_expires_at=? WHERE id=?",(token,(stamp+timedelta(minutes=5)).isoformat(),str(uid)))
        published=False
        try:
            source=partial if partial.exists() else destination
            if source.stat().st_size<row['received_bytes']:raise HTTPException(409,'upload_partial_unavailable')
            if source==partial:
                with source.open('r+b') as output:
                    output.truncate(row['received_bytes'])
                    if row['stream_format']=='pcm':
                        raw=body.bytes-44
                        if raw<=0 or raw%(row['stream_channels']*2):raise HTTPException(422,'invalid_pcm_frame_count')
                        output.seek(0);output.write(header(raw,row['stream_channels']))
                    output.flush();os.fsync(output.fileno())
            if file_sha256(source)!=body.sha256:raise HTTPException(422,'upload_integrity_failure')
            with database() as con:
                current=upload_row(con,eid,uid,actor);require_processing(con,eid);require_live_upload(current)
                if current['stream_seal_token']!=token:raise HTTPException(409,'live_upload_seal_changed')
                if source==partial:os.replace(partial,destination)
                con.execute("UPDATE uploads SET status='uploaded',expected_bytes=?,expected_sha256=?,stream_sealed=1,stream_seal_token=NULL,stream_seal_expires_at=NULL WHERE id=?",(body.bytes,body.sha256,str(uid)))
                audit(con,actor,'live_upload_sealed',str(uid))
            published=True
            return {'id':str(uid),'status':'uploaded','received_bytes':body.bytes}
        except OSError:raise HTTPException(503,'asset_storage_unavailable') from None
        finally:
            if not published:
                with database() as con:
                    con.execute("UPDATE uploads SET status='open',stream_seal_token=NULL,stream_seal_expires_at=NULL WHERE id=? AND stream_seal_token=?",(str(uid),token))

    @app.get('/v1/encounters/{eid}/stream-uploads')
    def pending(eid:UUID,actor=Depends(identity)):
        with database() as con:
            encounter(con,eid,actor)
            rows=con.execute("SELECT id,received_bytes,stream_format,stream_channels,media_type,created_at,expires_at FROM uploads WHERE encounter=? AND stream_format IS NOT NULL AND stream_sealed=0 AND received_bytes>44 ORDER BY created_at DESC",(str(eid),)).fetchall()
            return {'items':[dict(row) for row in rows]}

    @app.get('/v1/encounters/{eid}/stream-uploads/{uid}/recovery')
    def recovery(eid:UUID,uid:UUID,actor=Depends(identity)):
        with database() as con:
            row=upload_row(con,eid,uid,actor)
            if not row['stream_format'] or row['stream_sealed']:raise HTTPException(409,'not_an_unfinished_live_upload')
            audit(con,actor,'partial_recording_recovery',str(uid))
        path=assets/f'{uid}.resume.part'
        if not path.is_file():path=assets/f'{uid}.wav'
        if not path.is_file() or path.stat().st_size<row['received_bytes']:raise HTTPException(404,'partial_recording_unavailable')
        limit=row['received_bytes'];pcm=row['stream_format']=='pcm';offset=44 if pcm else 0
        if limit<=offset:raise HTTPException(409,'empty_recording_prefix')
        def chunks():
            with path.open('rb') as incoming:
                if pcm:yield header(limit-44,row['stream_channels'])
                incoming.seek(offset);left=limit-offset
                while left:
                    chunk=incoming.read(min(left,1024*1024))
                    if not chunk:raise OSError('Partial recording prefix unavailable')
                    yield chunk;left-=len(chunk)
        extension={'audio/wav':'wav','audio/webm':'webm','audio/ogg':'ogg','audio/mp4':'m4a'}[row['media_type']]
        return StreamingResponse(chunks(),media_type=row['media_type'],headers={'Content-Disposition':f'attachment; filename="partial-recovered-recording.{extension}"','X-Recording-Recovery':'partial_unverified'})
