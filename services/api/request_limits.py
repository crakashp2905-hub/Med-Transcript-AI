"""Streaming request bounds, including requests without Content-Length."""
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from services.api.ingest import MAX_UPLOAD_BYTES
from services.strict_json import loads


class RequestLimits:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        media_type = headers.get(b'content-type', b'').split(b';')[0].strip().lower()
        is_json = media_type == b'application/json' or media_type.endswith(b'+json')
        is_audio = media_type.startswith(b'audio/') or media_type == b'application/octet-stream'
        limit = MAX_UPLOAD_BYTES if is_audio and scope.get('path', '').endswith('/content') else 8*1024*1024
        length = headers.get(b'content-length', b'')
        if length.isdigit() and (len(length) > 12 or int(length) > limit):
            return await JSONResponse({'code': 'request_too_large'}, status_code=413)(scope, receive, send)
        size = 0
        if is_json:
            chunks = []
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                size += len(message.get('body', b''))
                if size > limit:
                    return await JSONResponse({'code': 'request_too_large'}, status_code=413)(scope, receive, send)
                chunks.append(message.get('body', b''))
                if not message.get('more_body', False):
                    break
            body = b''.join(chunks)
            if body:
                try:
                    loads(body)
                except (ValueError, UnicodeError):
                    return await JSONResponse({'code': 'invalid_json_structure'}, status_code=422)(scope, receive, send)
            delivered = False
            async def replay_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type': 'http.request', 'body': body, 'more_body': False}
                return await receive()
            return await self.app(scope, replay_receive, send)

        async def bounded_receive():
            nonlocal size
            message = await receive()
            size += len(message.get('body', b''))
            if size > limit:
                raise HTTPException(413, 'request_too_large')
            return message

        return await self.app(scope, bounded_receive, send)
