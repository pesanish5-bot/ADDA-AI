from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.auth.service import AuthService
from app.auth.store import MemoryUserStore
from app.config import Settings
from app.main import create_app
from app.task_store import MAX_TASKS_PER_USER, MemoryTaskStore

SECRET = 'test-task-history-secret-at-least-32-chars!!'


def _token(sub: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode({
        'sub': sub, 'email': f'{sub}@example.com', 'aud': 'adda-ai', 'token_use': 'id',
        'iat': now, 'exp': now + timedelta(hours=1),
    }, SECRET, algorithm='HS256')


def _client(store: MemoryTaskStore | None = None) -> tuple[TestClient, MemoryTaskStore]:
    settings = Settings(
        _env_file=None, nexus_provider='demo', auth_dev_jwt_secret=SECRET, auth_required=True,
    )
    task_store = store or MemoryTaskStore()
    app = create_app(
        settings,
        auth_service=AuthService(settings, MemoryUserStore()),
        task_store=task_store,
    )
    return TestClient(app), task_store


def test_chat_is_saved_and_owner_isolated():
    client, _ = _client()
    alice = {'Authorization': f'Bearer {_token("alice")}' }
    bob = {'Authorization': f'Bearer {_token("bob")}' }

    response = client.post('/api/chat', json={'message': 'Write a small function.'}, headers=alice)
    assert response.status_code == 200
    alice_tasks = client.get('/api/tasks', headers=alice)
    assert alice_tasks.status_code == 200
    assert alice_tasks.json()[0]['prompt'] == 'Write a small function.'
    assert alice_tasks.json()[0]['response']['request_id'] == response.json()['request_id']
    assert client.get('/api/tasks', headers=bob).json() == []


def test_archive_restore_and_delete_are_owner_scoped():
    client, _ = _client()
    alice = {'Authorization': f'Bearer {_token("alice")}' }
    bob = {'Authorization': f'Bearer {_token("bob")}' }
    task_id = client.post('/api/chat', json={'message': 'Explain a test.'}, headers=alice).json()['request_id']

    assert client.post(f'/api/tasks/{task_id}/archive', headers=bob).status_code == 404
    archived = client.post(f'/api/tasks/{task_id}/archive', headers=alice)
    assert archived.status_code == 200
    assert archived.json()['archived'] is True
    assert client.get('/api/tasks', headers=alice).json() == []
    assert len(client.get('/api/tasks?archived=true', headers=alice).json()) == 1

    restored = client.post(f'/api/tasks/{task_id}/restore', headers=alice)
    assert restored.status_code == 200
    assert restored.json()['archived'] is False
    assert client.delete(f'/api/tasks/{task_id}', headers=alice).json() == {'deleted': True}
    assert client.get('/api/tasks', headers=alice).json() == []


def test_history_requires_authentication_and_is_bounded():
    client, store = _client()
    assert client.get('/api/tasks').status_code == 401
    response = {
        'request_id': '', 'agent': 'coding', 'answer': 'ok', 'provider': 'demo',
        'activity': [], 'citations': [], 'usage': None,
    }
    for index in range(MAX_TASKS_PER_USER + 2):
        response['request_id'] = f'task-{index}'
        store.save_task('alice', f'Prompt {index}', response.copy())
    assert len(store.list_tasks('alice', archived=False)) == MAX_TASKS_PER_USER
