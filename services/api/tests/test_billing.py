import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.auth.service import AuthService
from app.auth.store import MemoryUserStore
from app.billing import MemoryBillingStore
from app.config import Settings
from app.main import create_app
from app.usage_store import MemoryUsageStore

SECRET = 'test-billing-jwt-secret-at-least-32-characters'
WEBHOOK_SECRET = 'whsec_test_secret'
PRICE_ID = 'price_pro_test'


class FakeStripe:
    def __init__(self) -> None:
        self.checkout_calls: list[tuple[str, str, str]] = []
        self.portal_calls: list[str] = []

    def create_checkout(self, user_id: str, email: str, customer_id: str = '') -> str:
        self.checkout_calls.append((user_id, email, customer_id))
        return 'https://checkout.stripe.com/c/pay/test'

    def create_portal(self, customer_id: str) -> str:
        self.portal_calls.append(customer_id)
        return 'https://billing.stripe.com/p/session/test'

    def list_invoices(self, _customer_id: str) -> list[dict]:
        return [{
            'id': 'in_1', 'number': 'ADDA-1', 'status': 'paid', 'currency': 'usd',
            'amount_due': 1000, 'amount_paid': 1000, 'created': 1,
            'hosted_invoice_url': 'https://invoice.stripe.com/i/test', 'invoice_pdf': None,
        }]

    def get_pro_offer(self) -> dict:
        return {'amount': 1000, 'currency': 'usd', 'interval': 'month'}


def _token(sub: str = 'alice') -> str:
    now = datetime.now(UTC)
    return jwt.encode({
        'sub': sub, 'email': f'{sub}@example.com', 'aud': 'adda-ai', 'token_use': 'id',
        'iat': now, 'exp': now + timedelta(hours=1),
    }, SECRET, algorithm='HS256')


def _headers(sub: str = 'alice') -> dict[str, str]:
    return {'Authorization': f'Bearer {_token(sub)}'}


def _client(*, configured: bool = True):
    settings = Settings(
        _env_file=None, nexus_provider='demo', allow_demo_fixture=True,
        auth_dev_jwt_secret=SECRET, auth_required=True,
        stripe_secret_key='sk_test_x' if configured else '',
        stripe_webhook_secret=WEBHOOK_SECRET if configured else '',
        stripe_pro_price_id=PRICE_ID if configured else '',
    )
    store = MemoryBillingStore()
    gateway = FakeStripe()
    app = create_app(
        settings, auth_service=AuthService(settings, MemoryUserStore()),
        usage_store=MemoryUsageStore(), billing_store=store,
        billing_gateway=gateway if configured else None,
    )
    return TestClient(app), store, gateway


def _signed(payload: dict) -> tuple[bytes, str]:
    raw = json.dumps(payload, separators=(',', ':')).encode()
    timestamp = int(time.time())
    digest = hmac.new(
        WEBHOOK_SECRET.encode(), f'{timestamp}.'.encode() + raw, hashlib.sha256
    ).hexdigest()
    return raw, f't={timestamp},v1={digest}'


def test_free_summary_and_disabled_checkout_are_honest():
    client, _, _ = _client(configured=False)
    summary = client.get('/api/billing', headers=_headers()).json()
    assert summary['configured'] is False
    assert summary['plan'] == 'free'
    response = client.post('/api/billing/checkout', headers=_headers())
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'billing_not_configured'


def test_checkout_and_portal_are_bound_to_authenticated_owner():
    client, store, gateway = _client()
    checkout = client.post('/api/billing/checkout', headers=_headers())
    assert checkout.status_code == 200
    assert checkout.json()['url'].startswith('https://checkout.stripe.com/')
    assert gateway.checkout_calls == [('alice', 'alice@example.com', '')]
    assert client.post('/api/billing/portal', headers=_headers()).status_code == 409

    store.update('alice', {'customer_id': 'cus_123'})
    portal = client.post('/api/billing/portal', headers=_headers())
    assert portal.status_code == 200
    assert gateway.portal_calls == ['cus_123']
    assert client.get('/api/billing', headers=_headers()).json()['invoices'][0]['status'] == 'paid'


def test_signed_webhook_grants_exact_price_entitlements_and_is_idempotent():
    client, _, _ = _client()
    event = {
        'id': 'evt_1', 'type': 'customer.subscription.updated',
        'data': {'object': {
            'id': 'sub_1', 'customer': 'cus_1', 'status': 'active',
            'metadata': {'adda_user_id': 'alice'},
            'items': {'data': [{'price': {'id': PRICE_ID}}]},
            'current_period_end': 2_000_000_000, 'cancel_at_period_end': False,
        }},
    }
    raw, signature = _signed(event)
    first = client.post(
        '/api/billing/webhook', content=raw, headers={'Stripe-Signature': signature}
    )
    second = client.post(
        '/api/billing/webhook', content=raw, headers={'Stripe-Signature': signature}
    )
    assert first.json() == {'received': True, 'processed': True}
    assert second.json() == {'received': True, 'processed': False}
    summary = client.get('/api/billing', headers=_headers()).json()
    assert summary['plan'] == 'pro'
    assert summary['pro_offer']['amount'] == 1000
    assert summary['entitlements']['daily_requests'] == 100
    assert client.get('/api/usage', headers=_headers()).json()['daily']['request_limit'] == 100


def test_wrong_price_and_invalid_signature_never_grant_pro():
    client, _, _ = _client()
    event = {
        'id': 'evt_wrong', 'type': 'customer.subscription.updated',
        'data': {'object': {
            'id': 'sub_wrong', 'customer': 'cus_wrong', 'status': 'active',
            'metadata': {'adda_user_id': 'alice'},
            'items': {'data': [{'price': {'id': 'price_attacker'}}]},
        }},
    }
    raw, signature = _signed(event)
    assert client.post(
        '/api/billing/webhook', content=raw, headers={'Stripe-Signature': 't=1,v1=bad'}
    ).status_code == 400
    assert client.post(
        '/api/billing/webhook', content=raw, headers={'Stripe-Signature': signature}
    ).status_code == 200
    assert client.get('/api/billing', headers=_headers()).json()['plan'] == 'free'


def test_billing_routes_require_authentication():
    client, _, _ = _client()
    assert client.get('/api/billing').status_code == 401
    assert client.post('/api/billing/checkout').status_code == 401
