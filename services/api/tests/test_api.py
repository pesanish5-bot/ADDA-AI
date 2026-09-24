import pytest
from botocore.exceptions import ClientError, ReadTimeoutError
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers import CodingProvider, ProviderError


@pytest.fixture
def client():
    return TestClient(create_app(Settings(_env_file=None, nexus_provider='demo', demo_access_token='')))


def test_first_route_runs_real_graph_with_honest_fixture(client):
    response = client.post('/api/chat', json={'message': 'Write a Python function to reverse a string.'})
    assert response.status_code == 200
    result = response.json()
    assert result['provider'] == 'demo'
    assert result['agent'] == 'coding'
    assert 'not an AI-generated answer' in result['answer']
    assert [a['step'] for a in result['activity']] == ['Router', 'Coding agent']
    assert result['citations'] == []
    assert result['request_id']


@pytest.mark.parametrize('message', ['', '   ', 'a' * 12001])
def test_rejects_invalid_messages(client, message):
    assert client.post('/api/chat', json={'message': message}).status_code == 422


def test_document_requires_upload(client):
    result = client.post('/api/chat', json={'message': 'Summarize this PDF', 'agent': 'document'})
    assert result.status_code == 200
    body = result.json()
    assert body['agent'] == 'document'
    assert 'Attach a PDF' in body['answer']
    assert body['citations'] == []


def test_web_research_requires_search_access(client):
    result = client.post('/api/chat', json={'message': 'Research battery storage'})
    assert result.status_code == 503
    assert result.json()['detail']['code'] == 'search_not_configured'


def test_search_without_key_is_not_fake_success(client):
    result = client.post('/api/chat', json={'message': 'Find latest news'})
    assert result.status_code == 503
    assert result.json()['detail']['code'] == 'search_not_configured'
    assert 'answer' not in result.json()


def test_explicit_coding_overrides_keywords(client):
    result = client.post('/api/chat', json={'message': 'Code a PDF parser', 'agent': 'coding'})
    assert result.status_code == 200


def test_unknown_agent_rejected(client):
    assert client.post('/api/chat', json={'message': 'hello', 'agent': 'admin'}).status_code == 422


def test_demo_access_token_required_when_configured():
    client = TestClient(create_app(Settings(_env_file=None, nexus_provider='demo', demo_access_token='test-secret')))
    assert client.get('/health').status_code == 200
    assert client.post('/api/chat', json={'message': 'code'}).status_code == 401
    assert client.post('/api/chat', json={'message': 'code'}, headers={'X-Demo-Token': 'wrong'}).status_code == 401
    assert client.post('/api/chat', json={'message': 'code'}, headers={'X-Demo-Token': 'test-secret'}).status_code == 200


def test_cors_allows_frontend(client):
    result = client.options('/api/chat', headers={
        'Origin': 'http://localhost:3000', 'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type,x-demo-token',
    })
    assert result.headers['access-control-allow-origin'] == 'http://localhost:3000'
    other = client.options('/api/chat', headers={
        'Origin': 'https://unrelated.example', 'Access-Control-Request-Method': 'POST',
    })
    assert 'access-control-allow-origin' not in other.headers


def test_bedrock_payload_and_answer(monkeypatch):
    class FakeBedrock:
        def converse(self, **kwargs):
            assert kwargs['modelId'] == 'test-model'
            assert kwargs['messages'][0]['content'][0]['text'] == 'Write code'
            assert kwargs['inferenceConfig']['maxTokens'] == 1200
            return {'output': {'message': {'content': [{'text': 'Generated answer'}]}}}

    monkeypatch.setattr('app.providers.boto3.client', lambda *a, **kw: FakeBedrock())
    client = TestClient(create_app(Settings(_env_file=None, nexus_provider='bedrock', bedrock_model_id='test-model', demo_access_token='')))
    result = client.post('/api/chat', json={'message': 'Write code'})
    assert result.status_code == 200
    assert result.json()['answer'] == 'Generated answer'
    assert result.json()['provider'] == 'bedrock'


def test_bedrock_failure_does_not_fallback_or_leak(monkeypatch):
    def fail(*args, **kwargs):
        raise ClientError({'Error': {'Code': 'AccessDeniedException', 'Message': 'sensitive-internal-detail'}}, 'Converse')

    monkeypatch.setattr('app.providers.boto3.client', fail)
    client = TestClient(create_app(Settings(_env_file=None, nexus_provider='bedrock', bedrock_model_id='test-model', demo_access_token='')))
    result = client.post('/api/chat', json={'message': 'code'})
    assert result.status_code == 502
    assert 'sensitive-internal-detail' not in result.text
    assert 'answer' not in result.json()


def test_missing_model_is_actionable():
    provider = CodingProvider(Settings(_env_file=None, nexus_provider='bedrock', bedrock_model_id=''))
    with pytest.raises(ProviderError, match='BEDROCK_MODEL_ID'):
        provider.generate('code')


def test_bedrock_timeout_is_retryable_error(monkeypatch):
    class SlowBedrock:
        def converse(self, **kwargs):
            raise ReadTimeoutError(endpoint_url='https://bedrock.example')

    monkeypatch.setattr('app.providers.boto3.client', lambda *a, **kw: SlowBedrock())
    client = TestClient(create_app(Settings(_env_file=None, nexus_provider='bedrock', bedrock_model_id='test-model', demo_access_token='')))
    result = client.post('/api/chat', json={'message': 'code'})
    assert result.status_code == 504
    assert result.json()['detail']['code'] == 'provider_timeout'


def test_health_does_not_invoke_model(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Health must not call AWS')

    monkeypatch.setattr('app.providers.boto3.client', forbidden)
    client = TestClient(create_app(Settings(_env_file=None, nexus_provider='bedrock',
                                            bedrock_model_id='anthropic.test-model')))
    result = client.get('/health')
    assert result.status_code == 200
    assert result.json()['provider'] == 'bedrock'
    assert result.json()['capabilities']['document'] is True
    assert result.json()['capabilities']['search'] is False
