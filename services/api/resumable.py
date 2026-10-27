"""Sequential, hash-checked upload chunks; offsets commit only after fsync."""
import hashlib
import os
from uuid import UUID, uuid4
from fastapi import Depends, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from services.api.ingest import file_sha256

MAX_CHUNK_BYTES = 4 * 1024 * 1024


def register(app, database, identity, upload_row, require_processing, require_live_upload, assets, audit):
    @app.patch('/v1/encounters/{encounter_id}/audio-uploads/{upload_id}/content')
    async def append(encounter_id: UUID, upload_id: UUID, request: Request,
                     offset: int = Header(alias='Upload-Offset', ge=0),
                     chunk_sha256: str = Header(alias='Upload-Chunk-SHA256', pattern='^[a-f0-9]{64}$'),
                     actor=Depends(identity)):
        def validate():
            with database() as con:
                row=upload_row(con,encounter_id,upload_id,actor)
                require_processing(con,encounter_id);require_live_upload(row)
                if request.headers.get('content-type','').split(';')[0].strip().lower()!=row['media_type']:
                    raise HTTPException(415,'unsupported_media')
        await run_in_threadpool(validate)
        data=bytearray()
        async for chunk in request.stream():
            if len(data)+len(chunk)>MAX_CHUNK_BYTES:raise HTTPException(413,'chunk_size_exceeded')
            data.extend(chunk)
        if not data or hashlib.sha256(data).hexdigest()!=chunk_sha256:
            raise HTTPException(422,'chunk_integrity_failure')
        def commit_chunk():
            partial=assets/f'{upload_id}.resume.part';destination=assets/f'{upload_id}.wav'
            with database() as con:
                row=upload_row(con,encounter_id,upload_id,actor)
                require_processing(con,encounter_id);require_live_upload(row)
                # Recover a rename that succeeded just before the database transaction died.
                if row['status']=='open' and destination.is_file():
                    if destination.stat().st_size==row['expected_bytes'] and file_sha256(destination)==row['expected_sha256']:
                        con.execute("UPDATE uploads SET status='uploaded',received_bytes=? WHERE id=?",(row['expected_bytes'],str(upload_id)))
                        return {'status':'uploaded','received_bytes':row['expected_bytes']}
                    raise HTTPException(409,'upload_integrity_failure')
                if row['status']!='open':
                    if row['status'] in ('uploaded','complete') and offset+len(data)<=row['expected_bytes']:
                        with destination.open('rb') as source:
                            source.seek(offset)
                            if source.read(len(data))==data:return {'status':row['status'],'received_bytes':row['expected_bytes']}
                    raise HTTPException(409,'upload_not_open')
                received=row['received_bytes']
                if offset<received and offset+len(data)<=received and partial.is_file():
                    with partial.open('rb') as source:
                        source.seek(offset)
                        if source.read(len(data))==data:return {'status':'open','received_bytes':received}
                if offset!=received:raise HTTPException(409,'upload_offset_mismatch')
                if offset+len(data)>row['expected_bytes']:raise HTTPException(413,'upload_size_exceeded')
                if received and (not partial.is_file() or partial.stat().st_size<received):
                    raise HTTPException(409,'upload_partial_unavailable')
                try:
                    with partial.open('r+b' if partial.exists() else 'w+b') as target:
                        target.truncate(received);target.seek(received);target.write(data);target.flush();os.fsync(target.fileno())
                    received+=len(data)
                    status='open'
                    if received==row['expected_bytes'] and not (row['stream_format'] and not row['stream_sealed']):
                        if file_sha256(partial)!=row['expected_sha256']:
                            partial.unlink(missing_ok=True)
                            con.execute("UPDATE uploads SET received_bytes=0 WHERE id=?",(str(upload_id),))
                            # Return an error response after committing the reset, permitting a clean retry.
                            from fastapi.responses import JSONResponse
                            return JSONResponse(status_code=422,content={'code':'upload_integrity_failure'})
                        os.replace(partial,destination);status='uploaded'
                    con.execute('UPDATE uploads SET received_bytes=?,status=? WHERE id=?',(received,status,str(upload_id)))
                    audit(con,actor,'upload_chunk_received',str(upload_id))
                    return {'status':status,'received_bytes':received}
                except OSError:
                    raise HTTPException(503,'asset_storage_unavailable') from None
        return await run_in_threadpool(commit_chunk)
