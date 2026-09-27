from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import Any, Protocol

import boto3
from botocore.exceptions import ClientError

MAX_TASKS_PER_USER = 100


def _now() -> str:
    return datetime.now(UTC).isoformat()


class TaskStore(Protocol):
    def save_task(self, user_id: str, prompt: str, response: dict[str, Any]) -> dict[str, Any]: ...

    def list_tasks(self, user_id: str, *, archived: bool) -> list[dict[str, Any]]: ...

    def set_archived(self, user_id: str, task_id: str, *, archived: bool) -> dict[str, Any] | None: ...

    def delete_task(self, user_id: str, task_id: str) -> bool: ...


class MemoryTaskStore:
    """Bounded process-local task storage for tests and local development."""

    def __init__(self) -> None:
        self.tasks: dict[str, dict[str, dict[str, Any]]] = {}
        self._lock = Lock()

    def save_task(self, user_id: str, prompt: str, response: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        task_id = str(response['request_id'])
        task = {
            'id': task_id,
            'prompt': prompt,
            'response': response,
            'created_at': now,
            'updated_at': now,
            'archived': False,
        }
        with self._lock:
            user_tasks = self.tasks.setdefault(user_id, {})
            user_tasks[task_id] = task
            if len(user_tasks) > MAX_TASKS_PER_USER:
                oldest = sorted(user_tasks.values(), key=lambda item: item['created_at'])
                for item in oldest[:len(user_tasks) - MAX_TASKS_PER_USER]:
                    user_tasks.pop(item['id'], None)
        return task.copy()

    def list_tasks(self, user_id: str, *, archived: bool) -> list[dict[str, Any]]:
        with self._lock:
            items = [
                item.copy() for item in self.tasks.get(user_id, {}).values()
                if bool(item.get('archived')) is archived
            ]
        return sorted(items, key=lambda item: item['created_at'], reverse=True)

    def set_archived(self, user_id: str, task_id: str, *, archived: bool) -> dict[str, Any] | None:
        with self._lock:
            task = self.tasks.get(user_id, {}).get(task_id)
            if not task:
                return None
            task['archived'] = archived
            task['updated_at'] = _now()
            return task.copy()

    def delete_task(self, user_id: str, task_id: str) -> bool:
        with self._lock:
            return self.tasks.get(user_id, {}).pop(task_id, None) is not None


class DynamoTaskStore:
    """Owner-partitioned durable task history in the existing profiles table."""

    def __init__(self, table_name: str, region: str) -> None:
        self.table = boto3.resource('dynamodb', region_name=region).Table(table_name)

    def save_task(self, user_id: str, prompt: str, response: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        task_id = str(response['request_id'])
        item = {
            'pk': f'USER#{user_id}',
            'sk': f'TASK#{task_id}',
            'id': task_id,
            'prompt': prompt,
            'response': response,
            'created_at': now,
            'updated_at': now,
            'archived': False,
            'entity_type': 'task',
        }
        self.table.put_item(Item=item)
        self._trim(user_id)
        return self._from_item(item)

    def list_tasks(self, user_id: str, *, archived: bool) -> list[dict[str, Any]]:
        items = [
            self._from_item(item) for item in self._query_all(user_id)
            if bool(item.get('archived')) is archived
        ]
        return sorted(items, key=lambda item: item['created_at'], reverse=True)

    def set_archived(self, user_id: str, task_id: str, *, archived: bool) -> dict[str, Any] | None:
        try:
            response = self.table.update_item(
                Key={'pk': f'USER#{user_id}', 'sk': f'TASK#{task_id}'},
                UpdateExpression='SET archived = :archived, updated_at = :updated',
                ConditionExpression='attribute_exists(pk)',
                ExpressionAttributeValues={':archived': archived, ':updated': _now()},
                ReturnValues='ALL_NEW',
            )
        except ClientError as exc:
            if exc.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                return None
            raise
        return self._from_item(response['Attributes'])

    def delete_task(self, user_id: str, task_id: str) -> bool:
        response = self.table.delete_item(
            Key={'pk': f'USER#{user_id}', 'sk': f'TASK#{task_id}'},
            ReturnValues='ALL_OLD',
        )
        return bool(response.get('Attributes'))

    def _trim(self, user_id: str) -> None:
        items = self._query_all(user_id, projection='pk, sk, created_at')
        if len(items) <= MAX_TASKS_PER_USER:
            return
        oldest = sorted(items, key=lambda item: str(item.get('created_at') or ''))
        with self.table.batch_writer() as batch:
            for item in oldest[:len(items) - MAX_TASKS_PER_USER]:
                batch.delete_item(Key={'pk': item['pk'], 'sk': item['sk']})

    def _query_all(self, user_id: str, *, projection: str | None = None) -> list[dict[str, Any]]:
        """Read the complete bounded partition even when DynamoDB paginates at 1 MB."""
        items: list[dict[str, Any]] = []
        start_key: dict[str, Any] | None = None
        while True:
            kwargs: dict[str, Any] = {
                'KeyConditionExpression': 'pk = :pk AND begins_with(sk, :prefix)',
                'ExpressionAttributeValues': {':pk': f'USER#{user_id}', ':prefix': 'TASK#'},
            }
            if projection:
                kwargs['ProjectionExpression'] = projection
            if start_key:
                kwargs['ExclusiveStartKey'] = start_key
            response = self.table.query(**kwargs)
            items.extend(response.get('Items', []))
            start_key = response.get('LastEvaluatedKey')
            if not start_key:
                return items

    @staticmethod
    def _from_item(item: dict[str, Any]) -> dict[str, Any]:
        return {
            'id': str(item.get('id') or str(item.get('sk', '')).removeprefix('TASK#')),
            'prompt': str(item.get('prompt') or ''),
            'response': item.get('response') or {},
            'created_at': str(item.get('created_at') or ''),
            'updated_at': str(item.get('updated_at') or item.get('created_at') or ''),
            'archived': bool(item.get('archived')),
        }
