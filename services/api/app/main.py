import logging
import secrets
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum

from app.agents.document import MAX_BYTES, DocumentStore
from app.agents.s3_document import S3DocumentStore
from app.body_limit import BodyLimit
from app.config import Settings
from app.graph import build_graph
from app.observability import RequestContext, annotate, configure_logging, current_request_id, log_event
from app.providers import CodingProvider, ProviderError
from app.ratelimit import RateLimit, RateLimiter
from app.schemas import ChatRequest, ChatResponse


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={'detail': {
        'code': code, 'message': message, 'request_id': current_request_id(),
    }})


def create_app(settings: Settings | None = None, provider: CodingProvider | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)
    for warning in settings.validate_for_environment():
        log_event('configuration warning', logging.WARNING, warning=warning)

    documents = S3DocumentStore(settings.document_bucket) if settings.document_bucket else DocumentStore()
    graph = build_graph(provider or CodingProvider(settings), documents)
    app = FastAPI(title='ADDA AI API', version=settings.app_version,
                  docs_url=None if settings.is_production else '/docs',
                  redoc_url=None, openapi_url=None if settings.is_production else '/openapi.json')

    # Starlette wraps in reverse order: the last middleware added runs first.
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.origins,
        allow_methods=['GET', 'POST', 'DELETE'],
        allow_headers=['Content-Type', 'X-Demo-Token', 'X-Document-Token', 'X-Request-ID'],
        expose_headers=['X-Request-ID', 'Retry-After'],
    )
    app.add_middleware(BodyLimit)
    limiter = RateLimiter(
        {'/api/chat': settings.rate_limit_chat_per_minute,
         '/api/documents': settings.rate_limit_upload_per_minute},
        settings.rate_limit_default_per_minute,
    )
    app.add_middleware(RateLimit, limiter=limiter, trust_proxy_headers=settings.trust_proxy_headers)
    app.add_middleware(RequestContext)

    @app.exception_handler(ProviderError)
    async def provider_error(_request: Request, exc: ProviderError):
        annotate(error_code=exc.code)
        return _error(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        annotate(error_code='invalid_request')
        return _error(422, 'invalid_request',
                      'Send a nonblank message of at most 12,000 characters and a supported agent.')

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {'code': 'http_error', 'message': str(exc.detail)}
        annotate(error_code=detail.get('code'))
        return _error(exc.status_code, detail.get('code', 'http_error'), detail.get('message', 'Request failed.'))

    @app.exception_handler(Exception)
    async def unhandled_error(_request: Request, exc: Exception):
        # Log the class and request id for operators; never return internals to clients.
        annotate(error_code='internal_error')
        log_event('unhandled exception', logging.ERROR, exception=type(exc).__name__)
        return _error(500, 'internal_error', 'Something went wrong on our side. Retry with the request ID if it persists.')

    def authorize(x_demo_token: str | None = Header(default=None)):
        if settings.demo_access_token and not secrets.compare_digest(
            (x_demo_token or '').encode(), settings.demo_access_token.encode()
        ):
            raise HTTPException(401, detail={'code': 'unauthorized', 'message': 'Enter the demo access token.'})

    @app.get('/health')
    def health():
        """Liveness: the process is up and configured. Makes no network calls."""
        return {'status': 'ok', 'environment': settings.app_env, 'version': settings.app_version,
                'provider': settings.nexus_provider,
                'capabilities': {'coding': True, 'document': settings.document_enabled,
                                 'search': settings.search_enabled, 'research': settings.document_enabled or settings.search_enabled},
                'limits': {'upload_bytes': MAX_BYTES, 'document_pages': 30, 'document_ttl_seconds': 3600},
                'research_mode': 'attached document, or Tavily when configured'}

    @app.get('/ready')
    def ready():
        """Readiness: dependencies this instance needs are reachable. Never invokes paid models."""
        checks = []
        if settings.nexus_provider == 'bedrock':
            checks.append({'check': 'bedrock_model_configured', 'ok': bool(settings.bedrock_model_id.strip())})
        else:
            checks.append({'check': 'coding_fixture_allowed',
                           'ok': settings.allow_demo_fixture or not settings.is_production})
        if settings.document_enabled and settings.document_bucket:
            try:
                documents.client.head_bucket(Bucket=settings.document_bucket)  # type: ignore[attr-defined]
                checks.append({'check': 'document_bucket', 'ok': True})
            except (BotoCoreError, ClientError, AttributeError):
                checks.append({'check': 'document_bucket', 'ok': False})
        status_code = 200 if all(item['ok'] for item in checks) else 503
        return JSONResponse(status_code=status_code, content={'ready': status_code == 200, 'checks': checks})

    @app.post('/api/documents', dependencies=[Depends(authorize)])
    def upload_document(file: UploadFile = File(...)):
        try:
            if not settings.document_enabled:
                raise ProviderError('Document storage is unavailable in this deployment.', 'documents_disabled', 503)
            data = file.file.read(MAX_BYTES + 1)
            result = documents.ingest(data, file.filename or 'upload')
            annotate(route='document_upload', pages=result['pages'])
            return result
        finally:
            file.file.close()

    @app.post('/api/documents/demo', dependencies=[Depends(authorize)])
    def demo_document():
        if not settings.document_enabled:
            raise ProviderError('Document storage is unavailable in this deployment.', 'documents_disabled', 503)
        source = Path(__file__).parent / 'samples' / 'atlas-project.pdf'
        annotate(route='document_sample')
        return documents.ingest(source.read_bytes(), source.name)

    @app.delete('/api/documents/{document_id}', dependencies=[Depends(authorize)])
    def delete_document(document_id: str, x_document_token: str = Header(default='')):
        documents.delete(document_id, x_document_token)
        annotate(route='document_delete')
        return {'deleted': True}

    @app.post('/api/chat', response_model=ChatResponse, dependencies=[Depends(authorize)])
    def chat(body: ChatRequest, x_document_token: str = Header(default='')):
        request_id = current_request_id()
        if body.document_id and not settings.document_enabled:
            raise ProviderError('Document storage is unavailable in this deployment.', 'documents_disabled', 503)
        annotate(route='chat', requested_agent=body.agent, has_document=bool(body.document_id))
        state = graph.invoke({'message': body.message, 'requested_agent': body.agent,
                              'agent': '', 'answer': '', 'activity': [], 'citations': [],
                              'document_id': body.document_id, 'document_token': x_document_token,
                              'provider': settings.nexus_provider, 'plan': [], 'collection': {}})
        annotate(agent=state['agent'], provider=state['provider'])
        return ChatResponse(request_id=request_id, agent=state['agent'], answer=state['answer'],
                            provider=state['provider'], activity=state['activity'],
                            citations=state.get('citations') or [])

    return app


app = create_app()
handler = Mangum(app, lifespan='off')
