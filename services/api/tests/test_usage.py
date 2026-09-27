from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.auth.service import AuthService
from app.auth.store import MemoryUserStore
from app.config import Settings
from app.main import create_app
from app.task_store import MemoryTaskStore
from app.usage_store import MemoryUsageStore

SECRET = 'test-usage-secret-at-least-32-characters!!'


class FakeBedrock:
    def __init__(self) -> None:
        self.calls = 0

    def converse(self, **_kwargs):
        self.calls += 1
        return {
            'output': {'message': {'content': [{'text': 'Generated answer'}]}},
            'stopReason': 'end_turn',
            'usage': {'inputTokens': 12, 'outputTokens': 8},
        }


def _token(sub: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode({
        'sub': sub, 'email': f'{sub}@example.com', 'aud': 'adda-ai', 'token_use': 'id',
        'iat': now, 'exp': now + timedelta(hours=1),
    }, SECRET, algorithm='HS256')


def _headers(sub: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {_token(sub)}'}


def _client(monkeypatch, **overrides) -> tuple[TestClient, FakeBedrock]:
    values = dict(
        _env_file=None,
        nexus_provider='bedrock',
        bedrock_model_id='test-model',
        auth_dev_jwt_secret=SECRET,
        auth_required=True,
        model_daily_request_limit=25,
        model_monthly_request_limit=250,
        model_daily_token_limit=50_000,
        model_monthly_token_limit=500_000,
    )
    values.update(overrides)
    settings = Settings(**values)
    fake = FakeBedrock()
    monkeypatch.setattr('app.providers.boto3.client', lambda *args, **kwargs: fake)
    app = create_app(
        settings,
        auth_service=AuthService(settings, MemoryUserStore()),
        task_store=MemoryTaskStore(),
        usage_store=MemoryUsageStore(),
    )
    return TestClient(app), fake


def test_model_usage_is_metered_and_owner_isolated(monkeypatch):
    client, fake = _client(monkeypatch)
    response = client.post(
        '/api/chat', json={'message': 'Write a Python function.', 'agent': 'coding'},
        headers=_headers('alice'),
    )
    assert response.status_code == 200
    assert fake.calls == 1

    alice = client.get('/api/usage', headers=_headers('alice')).json()
    bob = client.get('/api/usage', headers=_headers('bob')).json()
    assert alice['daily']['requests'] == 1
    assert alice['daily']['input_tokens'] == 12
    assert alice['daily']['output_tokens'] == 8
    assert alice['daily']['tokens'] == 20
    assert alice['monthly']['tokens'] == 20
    assert bob['daily']['requests'] == 0


def test_request_quota_blocks_before_paid_model_call(monkeypatch):
    client, fake = _client(
        monkeypatch, model_daily_request_limit=1, model_monthly_request_limit=10,
    )
    payload = {'message': 'Write a Python function.', 'agent': 'coding'}
    assert client.post('/api/chat', json=payload, headers=_headers('alice')).status_code == 200
    blocked = client.post('/api/chat', json=payload, headers=_headers('alice'))
    assert blocked.status_code == 429
    assert blocked.json()['detail']['code'] == 'usage_quota_exceeded'
    assert fake.calls == 1


def test_token_quota_blocks_the_next_model_request(monkeypatch):
    client, fake = _client(
        monkeypatch, model_daily_token_limit=20, model_monthly_token_limit=100,
    )
    payload = {'message': 'Write a Python function.', 'agent': 'coding'}
    assert client.post('/api/chat', json=payload, headers=_headers('alice')).status_code == 200
    blocked = client.post('/api/chat', json=payload, headers=_headers('alice'))
    assert blocked.status_code == 429
    assert fake.calls == 1


def test_non_model_document_route_does_not_consume_allowance(monkeypatch):
    client, fake = _client(monkeypatch)
    response = client.post(
        '/api/chat', json={'message': 'Summarize this document.', 'agent': 'document'},
        headers=_headers('alice'),
    )
    assert response.status_code == 200
    assert fake.calls == 0
    assert client.get('/api/usage', headers=_headers('alice')).json()['daily']['requests'] == 0


def test_usage_requires_authentication(monkeypatch):
    client, _ = _client(monkeypatch)
    assert client.get('/api/usage').status_code == 401
