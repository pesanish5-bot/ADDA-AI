import logging
import secrets
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum

from app.admin_store import AdminDirectory, DynamoAdminDirectory, MemoryAdminDirectory
from app.agents.document import MAX_BYTES, DocumentStore
from app.agents.s3_document import S3DocumentStore
from app.auth.routes import create_auth_router
from app.auth.service import AuthService
from app.auth.tokens import verify_bearer_token
from app.billing import (
    BillingError,
    BillingGateway,
    BillingStore,
    DynamoBillingStore,
    MemoryBillingStore,
    StripeGateway,
    billing_summary,
    process_stripe_event,
    verify_stripe_event,
)
from app.body_limit import BodyLimit
from app.config import Settings
from app.graph import build_graph, select_agent
from app.observability import RequestContext, annotate, configure_logging, current_request_id, log_event
from app.providers import CodingProvider, ProviderError
from app.ratelimit import RateLimit, RateLimiter
from app.schemas import BillingRedirect, BillingSummary, ChatRequest, ChatResponse, TaskRecord, UsageSummary
from app.task_store import DynamoTaskStore, MemoryTaskStore, TaskStore
from app.usage_store import DynamoUsageStore, MemoryUsageStore, QuotaExceeded, UsageStore


def _request_id(request: Request) -> str:
    return current_request_id() or getattr(request.state, 'request_id', '')


def _error(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={'detail': {
        'code': code, 'message': message, 'request_id': _request_id(request),
    }})


def create_app(
    settings: Settings | None = None,
    provider: CodingProvider | None = None,
    auth_service: AuthService | None = None,
    task_store: TaskStore | None = None,
    usage_store: UsageStore | None = None,
    billing_store: BillingStore | None = None,
    billing_gateway: BillingGateway | None = None,
    admin_directory: AdminDirectory | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)
    for warning in settings.validate_for_environment():
        log_event('configuration warning', logging.WARNING, warning=warning)

    documents = S3DocumentStore(settings.document_bucket) if settings.document_bucket else DocumentStore()
    coding_provider = provider or CodingProvider(settings)
    graph = build_graph(coding_provider, documents)
    auth = auth_service or AuthService(settings)
    tasks = task_store or (
        DynamoTaskStore(settings.auth_profiles_table, settings.cognito_pool_region)
        if settings.auth_profiles_table.strip() else MemoryTaskStore()
    )
    metering = usage_store or (
        DynamoUsageStore(settings.auth_profiles_table, settings.cognito_pool_region)
        if settings.auth_profiles_table.strip() else MemoryUsageStore()
    )
    billing = billing_store or (
        DynamoBillingStore(settings.auth_profiles_table, settings.cognito_pool_region)
        if settings.stripe_configured and settings.auth_profiles_table.strip()
        else MemoryBillingStore()
    )
    stripe = billing_gateway or (
        StripeGateway(
            settings.stripe_secret_key,
            settings.origins[0],
            settings.stripe_pro_price_id,
        ) if settings.stripe_configured else None
    )
    directory = admin_directory or (
        DynamoAdminDirectory(settings.auth_profiles_table, settings.cognito_pool_region)
        if settings.auth_profiles_table.strip()
        else MemoryAdminDirectory(auth.store)  # type: ignore[arg-type]
    )
    app = FastAPI(title='ADDA AI API', version=settings.app_version,
                  docs_url=None if settings.is_production else '/docs',
                  redoc_url=None, openapi_url=None if settings.is_production else '/openapi.json')

    # Starlette wraps in reverse order: the last middleware added runs first.
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.origins,
        allow_methods=['GET', 'POST', 'DELETE'],
        allow_headers=['Content-Type', 'Authorization', 'X-Demo-Token', 'X-Document-Token', 'X-Request-ID'],
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
    app.include_router(create_auth_router(settings, auth))

    @app.exception_handler(ProviderError)
    async def provider_error(request: Request, exc: ProviderError):
        annotate(error_code=exc.code)
        return _error(request, exc.status, exc.code, exc.message)

    @app.exception_handler(BillingError)
    async def billing_error(request: Request, exc: BillingError):
        annotate(error_code=exc.code)
        return _error(request, exc.status, exc.code, str(exc))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _exc: RequestValidationError):
        annotate(error_code='invalid_request')
        return _error(request, 422, 'invalid_request',
                      'Send a nonblank message of at most 12,000 characters and a supported agent.')

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {'code': 'http_error', 'message': str(exc.detail)}
        annotate(error_code=detail.get('code'))
        return _error(request, exc.status_code, detail.get('code', 'http_error'), detail.get('message', 'Request failed.'))

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        # Log the class and request id for operators; never return internals to clients.
        annotate(error_code='internal_error')
        log_event('unhandled exception', logging.ERROR, exception=type(exc).__name__,
                  request_id=_request_id(request))
        response = _error(request, 500, 'internal_error',
                          'Something went wrong on our side. Retry with the request ID if it persists.')
        # This response bypasses RequestContext (Starlette's error middleware is outermost).
        response.headers['X-Request-ID'] = _request_id(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-store'
        return response

    def authorize(
        x_demo_token: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict:
        if settings.demo_access_token and not secrets.compare_digest(
            (x_demo_token or '').encode(), settings.demo_access_token.encode()
        ):
            raise HTTPException(401, detail={'code': 'unauthorized', 'message': 'Enter the demo access token.'})
        if settings.api_requires_auth:
            scheme, _, token = (authorization or '').partition(' ')
            if scheme.lower() != 'bearer' or not token:
                raise HTTPException(401, detail={'code': 'unauthorized', 'message': 'Sign in required.'})
            claims = verify_bearer_token(
                token,
                region=settings.cognito_pool_region,
                user_pool_id=settings.cognito_user_pool_id,
                client_id=settings.cognito_client_id,
                dev_jwt_secret=settings.auth_dev_jwt_secret,
            )
            annotate(user_sub=str(claims.get('sub') or ''))
            try:
                auth.me(claims)
            except PermissionError:
                raise HTTPException(
                    403,
                    detail={'code': 'forbidden', 'message': 'This account is disabled.'},
                ) from None
            return claims
        return {}

    @app.get('/health')
    def health():
        """Liveness: the process is up and configured. Makes no network calls."""
        return {'status': 'ok', 'environment': settings.app_env, 'version': settings.app_version,
                'provider': settings.nexus_provider,
                'model': settings.bedrock_model_id if settings.nexus_provider == 'bedrock' else None,
                'models': coding_provider.model_options(),
                'auth': {
                    'configured': settings.auth_configured,
                    'provider': 'cognito' if settings.cognito_configured else (
                        'dev' if settings.auth_dev_jwt_secret else 'none'
                    ),
                    'required': settings.api_requires_auth,
                },
                'billing': {'configured': settings.stripe_configured, 'provider': 'stripe'},
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

    @app.post('/api/documents')
    def upload_document(file: UploadFile = File(...), claims: dict = Depends(authorize)):
        try:
            if not settings.document_enabled:
                raise ProviderError('Document storage is unavailable in this deployment.', 'documents_disabled', 503)
            data = file.file.read(MAX_BYTES + 1)
            result = documents.ingest(
                data, file.filename or 'upload', owner_id=str(claims.get('sub') or '')
            )
            annotate(route='document_upload', pages=result['pages'])
            return result
        finally:
            file.file.close()

    @app.post('/api/documents/demo')
    def demo_document(claims: dict = Depends(authorize)):
        if not settings.document_enabled:
            raise ProviderError('Document storage is unavailable in this deployment.', 'documents_disabled', 503)
        source = Path(__file__).parent / 'samples' / 'atlas-project.pdf'
        annotate(route='document_sample')
        return documents.ingest(
            source.read_bytes(), source.name, owner_id=str(claims.get('sub') or '')
        )

    @app.delete('/api/documents/{document_id}')
    def delete_document(
        document_id: str,
        x_document_token: str = Header(default=''),
        claims: dict = Depends(authorize),
    ):
        documents.delete(
            document_id, x_document_token, owner_id=str(claims.get('sub') or '')
        )
        annotate(route='document_delete')
        return {'deleted': True}

    def task_owner(claims: dict) -> str:
        user_id = str(claims.get('sub') or '')
        if not user_id:
            raise HTTPException(401, detail={'code': 'unauthorized', 'message': 'Sign in required.'})
        return user_id

    def usage_limits(user_id: str) -> dict[str, int]:
        record = billing.get(user_id)
        summary = billing_summary(
            record, settings.stripe_configured, settings.stripe_pro_price_id,
            settings.model_usage_limits, settings.pro_model_usage_limits,
        )
        return summary['entitlements']

    def require_admin(claims: dict = Depends(authorize)) -> dict:
        profile = auth.me(claims)
        if not profile.get('is_admin'):
            raise HTTPException(403, detail={
                'code': 'admin_required', 'message': 'Administrator access is required.',
            })
        return claims

    @app.get('/api/admin/overview')
    def admin_overview(_claims: dict = Depends(require_admin)):
        users = directory.list_users()
        enriched = []
        for user in users:
            user_id = str(user.get('id') or '')
            record = billing.get(user_id)
            plan = billing_summary(
                record, settings.stripe_configured, settings.stripe_pro_price_id,
                settings.model_usage_limits, settings.pro_model_usage_limits,
            )
            usage = metering.get_usage(user_id, plan['entitlements'])
            enriched.append({
                **user,
                'plan': plan['plan'],
                'subscription_status': plan['status'],
                'monthly_requests': usage['monthly']['requests'],
                'monthly_tokens': usage['monthly']['tokens'],
            })
        events = directory.list_auth_events()
        return {
            'summary': {
                'users': len(enriched),
                'active_users': sum(user.get('status') == 'active' for user in enriched),
                'pro_users': sum(user.get('plan') == 'pro' for user in enriched),
                'logins': sum(event.get('event_type') == 'login' and event.get('success') for event in events),
            },
            'users': enriched,
            'events': events,
        }

    @app.get('/api/tasks', response_model=list[TaskRecord])
    def list_tasks(archived: bool = False, claims: dict = Depends(authorize)):
        return tasks.list_tasks(task_owner(claims), archived=archived)

    @app.get('/api/usage', response_model=UsageSummary)
    def get_usage(claims: dict = Depends(authorize)):
        user_id = task_owner(claims)
        return metering.get_usage(user_id, usage_limits(user_id))

    @app.get('/api/billing', response_model=BillingSummary)
    def get_billing(claims: dict = Depends(authorize)):
        user_id = task_owner(claims)
        record = billing.get(user_id)
        invoices: list[dict] = []
        pro_offer: dict | None = None
        customer_id = str(record.get('customer_id') or '')
        if stripe:
            try:
                pro_offer = stripe.get_pro_offer()
                if customer_id:
                    invoices = stripe.list_invoices(customer_id)
            except BillingError as exc:
                log_event('billing summary enrichment failed', logging.WARNING,
                          exception=type(exc).__name__, user_id=user_id)
        return billing_summary(
            record, settings.stripe_configured, settings.stripe_pro_price_id,
            settings.model_usage_limits, settings.pro_model_usage_limits, invoices, pro_offer,
        )

    @app.post('/api/billing/checkout', response_model=BillingRedirect)
    def create_checkout(claims: dict = Depends(authorize)):
        if not stripe:
            raise BillingError(
                'Paid plans are not available yet.', 'billing_not_configured', 503
            )
        user_id = task_owner(claims)
        record = billing.get(user_id)
        if billing_summary(
            record, True, settings.stripe_pro_price_id,
            settings.model_usage_limits, settings.pro_model_usage_limits,
        )['plan'] == 'pro':
            raise BillingError(
                'Your Pro plan is already active. Use Manage billing instead.',
                'subscription_exists', 409,
            )
        email = str(claims.get('email') or claims.get('cognito:username') or '')
        return {'url': stripe.create_checkout(
            user_id, email, str(record.get('customer_id') or '')
        )}

    @app.post('/api/billing/portal', response_model=BillingRedirect)
    def create_billing_portal(claims: dict = Depends(authorize)):
        if not stripe:
            raise BillingError(
                'Billing management is not available yet.', 'billing_not_configured', 503
            )
        record = billing.get(task_owner(claims))
        customer_id = str(record.get('customer_id') or '')
        if not customer_id:
            raise BillingError(
                'No billing account exists for this user.', 'billing_customer_missing', 409
            )
        return {'url': stripe.create_portal(customer_id)}

    @app.post('/api/billing/webhook')
    async def stripe_webhook(
        request: Request, stripe_signature: str = Header(default='', alias='Stripe-Signature')
    ):
        if not settings.stripe_configured:
            raise BillingError(
                'Billing webhook is not configured.', 'billing_not_configured', 503
            )
        event = verify_stripe_event(
            await request.body(), stripe_signature, settings.stripe_webhook_secret
        )
        processed = process_stripe_event(event, billing, settings.stripe_pro_price_id)
        return {'received': True, 'processed': processed}

    @app.post('/api/tasks/{task_id}/archive', response_model=TaskRecord)
    def archive_task(task_id: str, claims: dict = Depends(authorize)):
        task = tasks.set_archived(task_owner(claims), task_id, archived=True)
        if not task:
            raise HTTPException(404, detail={'code': 'task_not_found', 'message': 'That task was not found.'})
        return task

    @app.post('/api/tasks/{task_id}/restore', response_model=TaskRecord)
    def restore_task(task_id: str, claims: dict = Depends(authorize)):
        task = tasks.set_archived(task_owner(claims), task_id, archived=False)
        if not task:
            raise HTTPException(404, detail={'code': 'task_not_found', 'message': 'That task was not found.'})
        return task

    @app.delete('/api/tasks/{task_id}')
    def delete_task(task_id: str, claims: dict = Depends(authorize)):
        tasks.delete_task(task_owner(claims), task_id)
        return {'deleted': True}

    @app.post('/api/chat', response_model=ChatResponse)
    def chat(
        body: ChatRequest,
        x_document_token: str = Header(default=''),
        claims: dict = Depends(authorize),
    ):
        request_id = current_request_id()
        if body.document_id and not settings.document_enabled:
            raise ProviderError('Document storage is unavailable in this deployment.', 'documents_disabled', 503)
        user_id = str(claims.get('sub') or '')
        routed_agent, _ = select_agent(body.message, body.agent, body.document_id)
        metered_request = bool(
            user_id and settings.nexus_provider == 'bedrock' and routed_agent == 'coding'
        )
        if metered_request:
            try:
                metering.begin_request(user_id, usage_limits(user_id))
            except QuotaExceeded as exc:
                raise ProviderError(str(exc), 'usage_quota_exceeded', 429) from None
        annotate(route='chat', requested_agent=body.agent, requested_model=body.model,
                 has_document=bool(body.document_id))
        state = graph.invoke({'message': body.message, 'requested_agent': body.agent,
                              'requested_model': body.model,
                              'agent': '', 'answer': '', 'activity': [], 'citations': [],
                              'document_id': body.document_id, 'document_token': x_document_token,
                              'provider': settings.nexus_provider, 'plan': [], 'collection': {},
                              'usage': None, 'user_id': str(claims.get('sub') or '')})
        usage = state.get('usage')
        annotate(agent=state['agent'], provider=state['provider'])
        if usage:
            annotate(model=usage.get('model'), input_tokens=usage.get('input_tokens'),
                     output_tokens=usage.get('output_tokens'), provider_latency_ms=usage.get('latency_ms'),
                     stop_reason=usage.get('stop_reason'), attempts=usage.get('attempts'))
            if metered_request:
                try:
                    metering.record_tokens(
                        user_id, int(usage.get('input_tokens') or 0),
                        int(usage.get('output_tokens') or 0),
                    )
                except Exception as exc:
                    log_event('usage metering persistence failed', logging.ERROR,
                              exception=type(exc).__name__, user_id=user_id)
        response = ChatResponse(request_id=request_id, agent=state['agent'], answer=state['answer'],
                                provider=state['provider'], activity=state['activity'],
                                citations=state.get('citations') or [], usage=usage)
        if user_id:
            try:
                tasks.save_task(user_id, body.message, response.model_dump(mode='json'))
            except Exception as exc:
                log_event('task history persistence failed', logging.ERROR,
                          exception=type(exc).__name__, user_id=user_id)
        return response

    return app


app = create_app()
handler = Mangum(app, lifespan='off')
