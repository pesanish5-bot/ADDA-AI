from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

import boto3
from boto3.dynamodb.conditions import Key

from app.auth.store import MemoryUserStore


class AdminDirectory(Protocol):
    def list_users(self, limit: int = 100) -> list[dict[str, Any]]: ...

    def list_auth_events(self, limit: int = 200) -> list[dict[str, Any]]: ...


def _serialized(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


class MemoryAdminDirectory:
    def __init__(self, store: MemoryUserStore) -> None:
        self.store = store

    def list_users(self, limit: int = 100) -> list[dict[str, Any]]:
        users = sorted(
            self.store.profiles.values(), key=lambda item: str(item.get('created_at') or ''),
            reverse=True,
        )[:limit]
        return [{key: _serialized(value) for key, value in item.items()} for item in users]

    def list_auth_events(self, limit: int = 200) -> list[dict[str, Any]]:
        events = sorted(
            self.store.events, key=lambda item: str(item.get('created_at') or ''), reverse=True,
        )[:limit]
        return [{key: _serialized(value) for key, value in item.items()} for item in events]


class DynamoAdminDirectory:
    """Bounded admin reads through the entity/time index; never scans the user table."""

    def __init__(self, table_name: str, region: str) -> None:
        self.table = boto3.resource('dynamodb', region_name=region).Table(table_name)

    def _by_type(self, entity_type: str, limit: int) -> list[dict[str, Any]]:
        response = self.table.query(
            IndexName='entity-created-index',
            KeyConditionExpression=Key('entity_type').eq(entity_type),
            ScanIndexForward=False,
            Limit=limit,
        )
        return response.get('Items') or []

    def list_users(self, limit: int = 100) -> list[dict[str, Any]]:
        return [{
            'id': item.get('id') or str(item.get('pk', '')).removeprefix('USER#'),
            'email': item.get('email') or '',
            'display_name': item.get('display_name') or '',
            'status': item.get('status') or 'active',
            'is_admin': bool(item.get('is_admin')),
            'login_count': int(item.get('login_count') or 0),
            'created_at': item.get('created_at'),
            'last_login_at': item.get('last_login_at'),
        } for item in self._by_type('profile', limit)]

    def list_auth_events(self, limit: int = 200) -> list[dict[str, Any]]:
        return [{
            'id': item.get('id'),
            'user_id': item.get('user_id'),
            'event_type': item.get('event_type') or 'unknown',
            'success': bool(item.get('success', True)),
            'created_at': item.get('created_at'),
        } for item in self._by_type('event', limit)]
