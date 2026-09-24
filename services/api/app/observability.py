"""Request correlation, structured JSON access logs and safe response headers.

Log lines never include prompts, document text, tokens or credentials. Handlers may
attach low-cardinality fields (agent, provider, error_code) through `annotate`.
"""
import json
import logging
import re
import sys
from contextvars import ContextVar
from time import perf_counter
from uuid import uuid4

REQUEST_ID_HEADER = b'x-request-id'
_SAFE_REQUEST_ID = re.compile(r'^[A-Za-z0-9._-]{8,64}$')

_request_id: ContextVar[str] = ContextVar('request_id', default='')
_annotations: ContextVar[dict | None] = ContextVar('annotations', default=None)

logger = logging.getLogger('adda.api')


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'ts': self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        extra = getattr(record, 'fields', None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload['exception'] = record.exc_info[0].__name__ if record.exc_info[0] else 'Exception'
        return json.dumps(payload, separators=(',', ':'), default=str)


def configure_logging(level: str = 'INFO') -> None:
    root = logging.getLogger()
    if any(getattr(handler, '_adda_json', False) for handler in root.handlers):
        root.setLevel(level.upper())
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler._adda_json = True  # type: ignore[attr-defined]
    root.handlers = [handler]
    root.setLevel(level.upper())
    # Uvicorn's default access log duplicates our structured line.
    logging.getLogger('uvicorn.access').disabled = True


def current_request_id() -> str:
    return _request_id.get()


def annotate(**fields: object) -> None:
    """Attach safe, low-cardinality fields to the current request's access log line."""
    current = _annotations.get()
    if current is not None:
        current.update({k: v for k, v in fields.items() if v is not None})


def log_event(message: str, level: int = logging.INFO, **fields: object) -> None:
    fields.setdefault('request_id', current_request_id())
    logger.log(level, message, extra={'fields': fields})


class RequestContext:
    """Pure ASGI middleware: request id, timing, access log, security headers."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        incoming = dict(scope.get('headers') or []).get(REQUEST_ID_HEADER, b'').decode('latin-1')
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid4().hex
        token = _request_id.set(request_id)
        fields_token = _annotations.set({})
        started = perf_counter()
        status = {'code': 500}

        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                status['code'] = message['status']
                headers = list(message.get('headers') or [])
                headers.append((REQUEST_ID_HEADER, request_id.encode()))
                headers.append((b'x-content-type-options', b'nosniff'))
                headers.append((b'referrer-policy', b'no-referrer'))
                if scope['path'].startswith('/api/'):
                    headers.append((b'cache-control', b'no-store'))
                message = {**message, 'headers': headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((perf_counter() - started) * 1000)
            fields = {
                'request_id': request_id,
                'method': scope['method'],
                'path': scope['path'],
                'status': status['code'],
                'duration_ms': duration_ms,
                **(_annotations.get() or {}),
            }
            level = logging.ERROR if status['code'] >= 500 else logging.WARNING if status['code'] >= 400 else logging.INFO
            logger.log(level, 'request', extra={'fields': fields})
            _annotations.reset(fields_token)
            _request_id.reset(token)
