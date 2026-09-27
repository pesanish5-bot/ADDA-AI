from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.auth.service import AuthService
from app.auth.store import MemoryUserStore
from app.config import Settings
from app.main import create_app

SECRET = 'test-admin-jwt-secret-at-least-32-characters'


def _headers(sub: str, email: str) -> dict[str, str]:
    now = datetime.now(UTC)
    token = jwt.encode({
        'sub': sub, 'email': email, 'aud': 'adda-ai', 'token_use': 'id',
        'iat': now, 'exp': now + timedelta(hours=1),
    }, SECRET, algorithm='HS256')
    return {'Authorization': f'Bearer {token}'}


def _client() -> TestClient:
    settings = Settings(
        _env_file=None, nexus_provider='demo', allow_demo_fixture=True,
        auth_dev_jwt_secret=SECRET, auth_required=True,
        admin_emails='owner@example.com',
    )
    store = MemoryUserStore()
    return TestClient(create_app(settings, auth_service=AuthService(settings, store)))


def test_admin_overview_lists_users_auth_activity_plan_and_usage():
    client = _client()
    owner = _headers('owner', 'owner@example.com')
    member = _headers('member', 'member@example.com')
    assert client.post('/api/auth/sync', headers=member, json={'event': 'login'}).status_code == 200
    assert client.post('/api/auth/sync', headers=member, json={'event': 'logout'}).status_code == 200

    response = client.get('/api/admin/overview', headers=owner)
    assert response.status_code == 200
    body = response.json()
    assert body['summary']['users'] == 2
    listed = {user['email']: user for user in body['users']}
    assert listed['owner@example.com']['is_admin'] is True
    assert listed['member@example.com']['plan'] == 'free'
    assert listed['member@example.com']['monthly_tokens'] == 0
    assert {event['event_type'] for event in body['events']} >= {'login', 'logout'}


def test_non_admin_and_anonymous_users_cannot_read_admin_data():
    client = _client()
    assert client.get('/api/admin/overview').status_code == 401
    response = client.get(
        '/api/admin/overview', headers=_headers('member', 'member@example.com')
    )
    assert response.status_code == 403
    assert response.json()['detail']['code'] == 'admin_required'
    assert client.get('/api/admin/billing-readiness').status_code == 401


def test_admin_billing_readiness_is_sanitized_when_disabled():
    response = _client().get(
        '/api/admin/billing-readiness', headers=_headers('owner', 'owner@example.com')
    )
    assert response.status_code == 200
    assert response.json() == {
        'status': 'disabled', 'configured': False, 'secret_source': 'none',
        'checks': [
            {'check': 'price_configured', 'ok': False},
            {'check': 'secure_secret_source', 'ok': True},
        ],
    }
