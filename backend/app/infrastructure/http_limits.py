"""Límite de cuerpo por stream antes de Pydantic/JSON, sin loggear contenido."""
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class BodyLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http' or scope['method'] in {'GET', 'HEAD'}:
            await self.app(scope, receive, send)
            return
        limit = 45 * 1024 * 1024 if scope['path'] == '/api/backups/upload' else 2 * 1024 * 1024
        chunks = []
        length = 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            part = message.get('body', b'')
            length += len(part)
            if length > limit:
                await JSONResponse({'detail': 'El archivo supera el tamaño admitido'}, status_code=413)(scope, receive, send)
                return
            chunks.append(part)
            if not message.get('more_body', False):
                break
        body = b''.join(chunks)
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': body}
            return await receive()
        await self.app(scope, bounded_receive, send)
