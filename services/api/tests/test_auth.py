from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.auth.service import AuthService
from app.auth.store import MemoryUserStore
from app.config import Settings
from app.main import create_app

SECRET = 'test-cognito-dev-jwt-secret-at-least-32-chars!!'


def _token(sub: str, email: str, *, exp_hours: int = 1, display_name: str = 'Test User') -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            'sub': sub,
            'email': email,
            'name': display_name,
            'aud': 'adda-ai',
            'token_use': 'id',
            'iat': now,
            'exp': now + timedelta(hours=exp_hours),
        },
        SECRET,
        algorithm='HS256',
    )


def _client(admin_emails: str = 'admin@example.com') -> TestClient:
    settings = Settings(
        _env_file=None,
        nexus_provider='demo',
        demo_access_token='',
        auth_dev_jwt_secret=SECRET,
        admin_emails=admin_emails,
        auth_required=False,
    )
    store = MemoryUserStore()
    return TestClient(create_app(settings, auth_service=AuthService(settings, store)))


def test_auth_status_and_sync_login():
    client = _client()
    assert client.get('/api/auth/status').json()['configured'] is True
    token = _token('user-1', 'alice@example.com', display_name='Alice')
    me = client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200
    assert me.json()['email'] == 'alice@example.com'
    synced = client.post(
        '/api/auth/sync',
        headers={'Authorization': f'Bearer {token}'},
        json={'event': 'login', 'display_name': 'Alice'},
    )
    assert synced.status_code == 200
    assert synced.json()['login_count'] == 1


def test_rejects_missing_and_expired_tokens():
    client = _client()
    assert client.get('/api/auth/me').status_code == 401
    expired = _token('user-2', 'bob@example.com', exp_hours=-1)
    assert client.get('/api/auth/me', headers={'Authorization': f'Bearer {expired}'}).status_code == 401


def test_health_reports_auth_block():
    client = _client()
    health = client.get('/health').json()
    assert health['auth']['configured'] is True
    assert health['auth']['required'] is False
    assert health['auth']['provider'] == 'dev'


def test_chat_requires_bearer_when_auth_required():
    settings = Settings(
        _env_file=None,
        nexus_provider='demo',
        demo_access_token='',
        auth_dev_jwt_secret=SECRET,
        auth_required=True,
    )
    client = TestClient(create_app(settings, auth_service=AuthService(settings, MemoryUserStore())))
    assert client.post('/api/chat', json={'message': 'code'}).status_code == 401
    token = _token('user-4', 'coder@example.com')
    ok = client.post('/api/chat', json={'message': 'code'}, headers={'Authorization': f'Bearer {token}'})
    assert ok.status_code == 200


def test_disabled_user_cannot_use_workspace_routes():
    settings = Settings(
        _env_file=None,
        nexus_provider='demo',
        auth_dev_jwt_secret=SECRET,
        auth_required=True,
    )
    store = MemoryUserStore()
    store.upsert_profile('disabled-user', 'disabled@example.com')
    store.profiles['disabled-user']['status'] = 'disabled'
    client = TestClient(create_app(settings, auth_service=AuthService(settings, store)))
    token = _token('disabled-user', 'disabled@example.com')
    response = client.post(
        '/api/chat',
        json={'message': 'code'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == 403
    assert response.json()['detail']['code'] == 'forbidden'
