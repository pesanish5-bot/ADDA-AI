"""Bedrock provider guardrails: limits, retries, truncation, usage metadata, safe failures."""
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi.testclient import TestClient

from app.config import ConfigurationError, Settings
from app.main import create_app
from app.providers import DEMO_ANSWER, TRUNCATION_NOTE, CodingProvider, ProviderError


def bedrock_settings(**overrides) -> Settings:
    base = dict(_env_file=None, nexus_provider='bedrock', bedrock_model_id='global.test-model', demo_access_token='')
    base.update(overrides)
    return Settings(**base)


def converse_response(text='def f(): pass', stop='end_turn', usage=None):
    return {'output': {'message': {'content': [{'text': text}]}}, 'stopReason': stop,
            'usage': usage if usage is not None else {'inputTokens': 42, 'outputTokens': 17}}


class FakeBedrock:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def client_error(code):
    return ClientError({'Error': {'Code': code, 'Message': 'internal detail'}}, 'Converse')


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr('app.providers.sleep', lambda *_: None)


def test_generation_carries_usage_and_respects_token_cap(monkeypatch):
    fake = FakeBedrock([converse_response()])
    monkeypatch.setattr('app.providers.boto3.client', lambda *a, **kw: fake)
    provider = CodingProvider(bedrock_settings(bedrock_max_tokens=800))
    generation = provider.generate('Write code', max_tokens=5000)  # caller asks for more than allowed
    assert fake.calls[0]['inferenceConfig']['maxTokens'] == 800
    assert fake.calls[0]['modelId'] == 'global.test-model'
    assert generation.provider == 'bedrock'
    assert generation.input_tokens == 42 and generation.output_tokens == 17
    assert generation.truncated is False and generation.attempts == 1
    assert 'text' not in generation.usage()


def test_client_is_reused_across_requests(monkeypatch):
    created = []

    def factory(*a, **kw):
        created.append(1)
        return FakeBedrock([converse_response(), converse_response()])

    monkeypatch.setattr('app.providers.boto3.client', factory)
    provider = CodingProvider(bedrock_settings())
    provider.generate('one')
    provider.generate('two')
    assert len(created) == 1


def test_truncated_output_is_flagged_and_annotated(monkeypatch):
    monkeypatch.setattr('app.providers.boto3.client',
                        lambda *a, **kw: FakeBedrock([converse_response('partial', stop='max_tokens')]))
    generation = CodingProvider(bedrock_settings()).generate('long task')
    assert generation.truncated is True
    assert generation.text.endswith(TRUNCATION_NOTE)


def test_throttling_is_retried_once_then_succeeds(monkeypatch, no_sleep):
    fake = FakeBedrock([client_error('ThrottlingException'), converse_response()])
    monkeypatch.setattr('app.providers.boto3.client', lambda *a, **kw: fake)
    generation = CodingProvider(bedrock_settings(bedrock_max_attempts=2)).generate('code')
    assert generation.attempts == 2
    assert len(fake.calls) == 2


def test_retry_budget_is_bounded(monkeypatch, no_sleep):
    fake = FakeBedrock([client_error('ThrottlingException'), client_error('ThrottlingException'),
                        converse_response()])
    monkeypatch.setattr('app.providers.boto3.client', lambda *a, **kw: fake)
    with pytest.raises(ProviderError) as info:
        CodingProvider(bedrock_settings(bedrock_max_attempts=2)).generate('code')
    assert info.value.code == 'provider_rate_limited'
    assert len(fake.calls) == 2  # never a third attempt


@pytest.mark.parametrize('code', ['AccessDeniedException', 'ValidationException', 'ExpiredTokenException'])
def test_non_retryable_errors_fail_fast(monkeypatch, no_sleep, code):
    fake = FakeBedrock([client_error(code), converse_response()])
    monkeypatch.setattr('app.providers.boto3.client', lambda *a, **kw: fake)
    with pytest.raises(ProviderError) as info:
        CodingProvider(bedrock_settings()).generate('code')
    assert len(fake.calls) == 1
    assert 'internal detail' not in info.value.message


def test_connection_error_maps_to_safe_provider_error(monkeypatch):
    fake = FakeBedrock([EndpointConnectionError(endpoint_url='https://bedrock.example')])
    monkeypatch.setattr('app.providers.boto3.client', lambda *a, **kw: fake)
    with pytest.raises(ProviderError) as info:
        CodingProvider(bedrock_settings()).generate('code')
    assert info.value.code == 'provider_unavailable'
    assert 'bedrock.example' not in info.value.message


def test_empty_model_output_is_an_error(monkeypatch):
    monkeypatch.setattr('app.providers.boto3.client',
                        lambda *a, **kw: FakeBedrock([{'output': {'message': {'content': []}}}]))
    with pytest.raises(ProviderError):
        CodingProvider(bedrock_settings()).generate('code')


def test_api_returns_usage_and_logs_metadata_without_prompt(monkeypatch, caplog):
    import logging
    caplog.set_level(logging.INFO, logger='adda.api')
    monkeypatch.setattr('app.providers.boto3.client', lambda *a, **kw: FakeBedrock([converse_response('answer')]))
    client = TestClient(create_app(bedrock_settings()))
    response = client.post('/api/chat', json={'message': 'Write a Python function SECRET-MARKER'})
    assert response.status_code == 200
    body = response.json()
    assert body['provider'] == 'bedrock'
    assert body['usage']['model'] == 'global.test-model'
    assert body['usage']['input_tokens'] == 42
    assert 'global.test-model' in body['activity'][-1]['detail']
    record = [r for r in caplog.records if r.getMessage() == 'request'][-1]
    fields = record.fields  # type: ignore[attr-defined]
    assert fields['model'] == 'global.test-model'
    assert fields['input_tokens'] == 42 and fields['output_tokens'] == 17
    assert 'SECRET-MARKER' not in str(fields)


def test_health_exposes_model_only_for_bedrock(monkeypatch):
    monkeypatch.setattr('app.providers.boto3.client', lambda *a, **kw: FakeBedrock([]))
    assert TestClient(create_app(bedrock_settings())).get('/health').json()['model'] == 'global.test-model'
    demo = TestClient(create_app(Settings(_env_file=None, nexus_provider='demo', demo_access_token='')))
    assert demo.get('/health').json()['model'] is None


def test_demo_fixture_is_explicit_and_labelled():
    generation = CodingProvider(Settings(_env_file=None, nexus_provider='demo')).generate('anything')
    assert generation.text == DEMO_ANSWER
    assert generation.provider == 'demo' and generation.model == 'fixture'
    assert 'not an AI-generated answer' in generation.text


def test_production_bedrock_failure_returns_error_not_fixture(monkeypatch):
    monkeypatch.setattr('app.providers.boto3.client',
                        lambda *a, **kw: FakeBedrock([client_error('ServiceUnavailableException'),
                                                      client_error('ServiceUnavailableException')]))
    monkeypatch.setattr('app.providers.sleep', lambda *_: None)
    client = TestClient(create_app(bedrock_settings(app_env='production', allowed_origins='https://app.example.com')))
    response = client.post('/api/chat', json={'message': 'Write code'})
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'provider_unavailable'
    assert 'Offline connection test' not in response.text


@pytest.mark.parametrize('field,value', [
    ('bedrock_max_tokens', 0), ('bedrock_max_tokens', 9000),
    ('bedrock_timeout_seconds', 30), ('bedrock_max_attempts', 5),
])
def test_out_of_range_limits_are_rejected_at_startup(field, value):
    with pytest.raises(ConfigurationError):
        bedrock_settings(**{field: value}).validate_for_environment()
