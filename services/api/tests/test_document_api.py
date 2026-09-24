import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.graph import select_agent


@pytest.fixture
def client():
    return TestClient(create_app(Settings(_env_file=None, nexus_provider='demo', tavily_api_key='', demo_access_token='')))


def test_demo_pdf_to_cited_answer_and_research_chain(client):
    doc = client.post('/api/documents/demo').json()
    assert doc['pages'] == 3
    headers = {'X-Document-Token': doc['document_token']}
    body = {'message': 'What is the approved budget?', 'document_id': doc['document_id']}
    result = client.post('/api/chat', json=body, headers=headers)
    assert result.status_code == 200
    data = result.json()
    assert data['agent'] == 'document'
    assert data['provider'] == 'extractive'
    assert data['citations'][0]['page'] == 2
    assert '180,000' in data['citations'][0]['excerpt']
    research = client.post('/api/chat', json={**body, 'message': 'Research the delivery risks and budget'}, headers=headers)
    assert research.status_code == 200
    data = research.json()
    assert data['agent'] == 'research'
    assert [a['step'] for a in data['activity']] == ['Router', 'Research plan', 'Collect evidence', 'Evidence brief']
    assert 'no AI synthesis' in data['answer']
    assert data['citations']


def test_token_required_for_query_and_delete(client):
    doc = client.post('/api/documents/demo').json()
    body = {'message': 'budget', 'document_id': doc['document_id']}
    assert client.post('/api/chat', json=body).status_code == 404
    assert client.delete('/api/documents/' + doc['document_id']).status_code == 404
    headers = {'X-Document-Token': doc['document_token']}
    assert client.delete('/api/documents/' + doc['document_id'], headers=headers).status_code == 200
    assert client.post('/api/chat', json=body, headers=headers).status_code == 404


def test_txt_upload_and_unsupported_question(client):
    result = client.post('/api/documents', files={'file': ('notes.txt', b'Batteries cost 200 rupees.', 'text/plain')})
    assert result.status_code == 200
    doc = result.json()
    result = client.post('/api/chat', json={'message': 'Who invented submarines?', 'document_id': doc['document_id']}, headers={'X-Document-Token': doc['document_token']})
    assert result.json()['citations'] == []
    assert 'Insufficient evidence' in result.json()['answer']


def test_upload_gate_and_oversize_body(client):
    assert client.post('/api/documents', files={'file': ('bad.exe', b'bad')}).status_code == 415
    assert client.post('/api/documents', content=b'a' * (6 * 1024 * 1024)).status_code == 413
    protected = TestClient(create_app(Settings(_env_file=None, demo_access_token='secret')))
    assert protected.post('/api/documents/demo').status_code == 401


def test_lambda_without_persistent_storage_disables_documents():
    client = TestClient(create_app(Settings(_env_file=None, document_enabled=False, tavily_api_key='')))
    assert client.get('/health').json()['capabilities']['document'] is False
    assert client.post('/api/documents/demo').status_code == 503


@pytest.mark.parametrize('message,document_id,expected', [
    ('Write a Python function to search a list', None, 'coding'),
    ('Explain this code and identify the bug', None, 'coding'),
    ('Find latest Python news', None, 'search'),
    ('Compare React components and fix the code', None, 'coding'),
    ('Research solar energy limitations', None, 'research'),
    ('Summarize the uploaded PDF', None, 'document'),
    ('Summarize the uploaded PDF', 'doc-1', 'document'),
    ('What is the approved budget?', None, 'search'),
    ('What is the approved budget?', 'doc-1', 'document'),
    ('What are the latest developments in AI agents?', None, 'search'),
])
def test_intent_routing_regressions(message, document_id, expected):
    assert select_agent(message, 'auto', document_id)[0] == expected
