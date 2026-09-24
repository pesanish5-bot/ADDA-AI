"""Production-baseline behaviour: correlation, limits, environment guards, safe errors."""
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.config import ConfigurationError, Settings
from app.main import create_app
from app.ratelimit import RateLimiter


def make_client(**overrides) -> TestClient:
    base = dict(_env_file=None, nexus_provider='demo', demo_access_token='')
    base.update(overrides)
    return TestClient(create_app(Settings(**base)), raise_server_exceptions=False)


def test_request_id_is_generated_and_returned():
    client = make_client()
    response = client.post('/api/chat', json={'message': 'Write a Python function'})
    assert response.status_code == 200
    header = response.headers['x-request-id']
    assert len(header) == 32
    assert response.json()['request_id'] == header


def test_safe_incoming_request_id_is_propagated_and_unsafe_is_replaced():
    client = make_client()
    ok = client.get('/health', headers={'X-Request-ID': 'trace-abc-12345'})
    assert ok.headers['x-request-id'] == 'trace-abc-12345'
    bad = client.get('/health', headers={'X-Request-ID': '<script>alert(1)</script>'})
    assert bad.headers['x-request-id'] != '<script>alert(1)</script>'


def test_error_responses_carry_request_id_and_security_headers():
    client = make_client()
    response = client.post('/api/chat', json={'message': ''})
    assert response.status_code == 422
    body = response.json()['detail']
    assert body['code'] == 'invalid_request'
    assert body['request_id'] == response.headers['x-request-id']
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['cache-control'] == 'no-store'


def test_unhandled_exception_returns_json_without_internals():
    settings = Settings(_env_file=None, nexus_provider='demo', demo_access_token='')

    class BrokenProvider:
        def __init__(self):
            self.settings = settings

        def generate(self, message, **kwargs):
            raise RuntimeError('database password is hunter2')

    client = TestClient(create_app(settings, provider=BrokenProvider()), raise_server_exceptions=False)  # type: ignore[arg-type]
    response = client.post('/api/chat', json={'message': 'Write a Python function'})
    assert response.status_code == 500
    assert response.json()['detail']['code'] == 'internal_error'
    assert 'hunter2' not in response.text
    assert 'RuntimeError' not in response.text


def test_access_log_is_json_without_prompt_text(caplog):
    client = make_client()
    caplog.set_level(logging.INFO, logger='adda.api')
    client.post('/api/chat', json={'message': 'SECRET-PROMPT write python code'})
    records = [r for r in caplog.records if r.getMessage() == 'request']
    assert records, 'expected an access log record'
    fields = records[-1].fields  # type: ignore[attr-defined]
    assert fields['path'] == '/api/chat'
    assert fields['status'] == 200
    assert fields['agent'] == 'coding'
    assert fields['provider'] == 'demo'
    assert 'SECRET-PROMPT' not in json.dumps(fields)


def test_rate_limiter_blocks_after_limit_and_resets():
    now = [0.0]
    limiter = RateLimiter({'/api/chat': 2}, default_limit=5, window_seconds=60, clock=lambda: now[0])
    assert limiter.check('1.1.1.1', '/api/chat')[0] is True
    assert limiter.check('1.1.1.1', '/api/chat')[0] is True
    blocked, remaining, retry = limiter.check('1.1.1.1', '/api/chat')
    assert blocked is False and remaining == 0 and retry >= 1
    assert limiter.check('2.2.2.2', '/api/chat')[0] is True  # other client unaffected
    now[0] = 61.0
    assert limiter.check('1.1.1.1', '/api/chat')[0] is True


def test_rate_limit_returns_429_with_retry_after():
    client = make_client(rate_limit_chat_per_minute=2)
    for _ in range(2):
        assert client.post('/api/chat', json={'message': 'Write python code'}).status_code == 200
    response = client.post('/api/chat', json={'message': 'Write python code'})
    assert response.status_code == 429
    assert response.json()['detail']['code'] == 'rate_limited'
    assert int(response.headers['retry-after']) >= 1
    # Read-only endpoints are not limited.
    assert client.get('/health').status_code == 200


def test_production_refuses_demo_fixture_by_default():
    with pytest.raises(ConfigurationError, match='fixture'):
        create_app(Settings(_env_file=None, app_env='production', nexus_provider='demo',
                            allowed_origins='https://app.example.com'))


def test_production_requires_https_origins_and_model_id():
    with pytest.raises(ConfigurationError, match='https'):
        Settings(_env_file=None, app_env='staging', nexus_provider='bedrock', bedrock_model_id='m',
                 allowed_origins='http://app.example.com').validate_for_environment()
    with pytest.raises(ConfigurationError, match='BEDROCK_MODEL_ID'):
        Settings(_env_file=None, nexus_provider='bedrock', bedrock_model_id='').validate_for_environment()


def test_production_with_explicit_fixture_flag_starts_and_hides_docs():
    app = create_app(Settings(_env_file=None, app_env='production', nexus_provider='demo',
                              allow_demo_fixture=True, allowed_origins='https://app.example.com',
                              document_enabled=False))
    client = TestClient(app)
    assert client.get('/docs').status_code == 404
    assert client.get('/openapi.json').status_code == 404
    health = client.get('/health').json()
    assert health['environment'] == 'production'


def test_ready_reports_checks(monkeypatch):
    client = make_client()
    ready = client.get('/ready')
    assert ready.status_code == 200
    assert ready.json()['ready'] is True

    class FailingS3:
        def head_bucket(self, **kwargs):
            from botocore.exceptions import ClientError
            raise ClientError({'Error': {'Code': '403'}}, 'HeadBucket')

    from app.agents.s3_document import S3DocumentStore
    monkeypatch.setattr('app.main.S3DocumentStore',
                        lambda bucket: S3DocumentStore(bucket, client=FailingS3()))
    broken = TestClient(create_app(Settings(_env_file=None, nexus_provider='demo', document_bucket='private-bucket')))
    response = broken.get('/ready')
    assert response.status_code == 503
    assert {'check': 'document_bucket', 'ok': False} in response.json()['checks']


def test_development_warns_but_runs_with_fixture():
    warnings = Settings(_env_file=None, nexus_provider='demo').validate_for_environment()
    assert any('fixture' in w for w in warnings)
