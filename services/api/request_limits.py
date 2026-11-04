"""Streaming request bounds, including requests without Content-Length."""
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from services.api.ingest import MAX_UPLOAD_BYTES


class RequestLimits:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        limit = 8 * 1024 * 1024 if headers.get(b'content-type', b'').split(b';')[0] == b'application/json' else MAX_UPLOAD_BYTES
        length = headers.get(b'content-length', b'')
        if length.isdigit() and (len(length) > 12 or int(length) > limit):
            return await JSONResponse({'code': 'request_too_large'}, status_code=413)(scope, receive, send)
        size = 0

        async def bounded_receive():
            nonlocal size
            message = await receive()
            size += len(message.get('body', b''))
            if size > limit:
                raise HTTPException(413, 'request_too_large')
            return message

        return await self.app(scope, bounded_receive, send)
