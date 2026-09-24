from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserStore(Protocol):
    def upsert_profile(
        self, user_id: str, email: str, display_name: str = '', is_admin: bool = False
    ) -> dict[str, Any]: ...

    def get_profile(self, user_id: str) -> dict[str, Any] | None: ...

    def record_login(self, user_id: str) -> dict[str, Any] | None: ...

    def record_event(
        self, user_id: str | None, event_type: str, success: bool = True, metadata: dict | None = None
    ) -> None: ...


class MemoryUserStore:
    """In-memory store for local tests and when DynamoDB is not configured."""

    def __init__(self) -> None:
        self.profiles: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self._event_id = 0

    def upsert_profile(
        self, user_id: str, email: str, display_name: str = '', is_admin: bool = False
    ) -> dict[str, Any]:
        existing = self.profiles.get(user_id)
        now = _now()
        if existing:
            existing['email'] = email.lower()
            if display_name:
                existing['display_name'] = display_name
            if is_admin:
                existing['is_admin'] = True
            existing['updated_at'] = now
            return existing
        profile = {
            'id': user_id,
            'email': email.lower(),
            'display_name': display_name or email.split('@')[0],
            'status': 'active',
            'is_admin': is_admin,
            'login_count': 0,
            'created_at': now,
            'updated_at': now,
            'last_login_at': None,
        }
        self.profiles[user_id] = profile
        return profile

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        return self.profiles.get(user_id)

    def record_login(self, user_id: str) -> dict[str, Any] | None:
        profile = self.profiles.get(user_id)
        if not profile:
            return None
        profile['login_count'] = int(profile.get('login_count') or 0) + 1
        profile['last_login_at'] = _now()
        profile['updated_at'] = profile['last_login_at']
        return profile

    def record_event(
        self, user_id: str | None, event_type: str, success: bool = True, metadata: dict | None = None
    ) -> None:
        self._event_id += 1
        self.events.append({
            'id': self._event_id,
            'user_id': user_id,
            'event_type': event_type,
            'success': success,
            'metadata': metadata or {},
            'created_at': _now(),
        })


class DynamoUserStore:
    """Persists profiles and auth events in DynamoDB (same AWS account as Cognito/Bedrock)."""

    def __init__(self, table_name: str, region: str) -> None:
        import boto3

        self.table = boto3.resource('dynamodb', region_name=region).Table(table_name)

    def upsert_profile(
        self, user_id: str, email: str, display_name: str = '', is_admin: bool = False
    ) -> dict[str, Any]:
        existing = self.get_profile(user_id)
        now = _now().isoformat()
        if existing:
            names = ['email = :email', 'updated_at = :updated']
            values: dict[str, Any] = {':email': email.lower(), ':updated': now}
            if display_name:
                names.append('display_name = :name')
                values[':name'] = display_name
            if is_admin:
                names.append('is_admin = :admin')
                values[':admin'] = True
            response = self.table.update_item(
                Key={'pk': f'USER#{user_id}', 'sk': 'PROFILE'},
                UpdateExpression='SET ' + ', '.join(names),
                ExpressionAttributeValues=values,
                ReturnValues='ALL_NEW',
            )
            return self._profile_from_item(response['Attributes'])
        item = {
            'pk': f'USER#{user_id}',
            'sk': 'PROFILE',
            'id': user_id,
            'email': email.lower(),
            'display_name': display_name or email.split('@')[0],
            'status': 'active',
            'is_admin': is_admin,
            'login_count': 0,
            'created_at': now,
            'updated_at': now,
            'entity_type': 'profile',
        }
        self.table.put_item(Item=item)
        return self._profile_from_item(item)

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        response = self.table.get_item(Key={'pk': f'USER#{user_id}', 'sk': 'PROFILE'})
        item = response.get('Item')
        return self._profile_from_item(item) if item else None

    def record_login(self, user_id: str) -> dict[str, Any] | None:
        now = _now().isoformat()
        try:
            response = self.table.update_item(
                Key={'pk': f'USER#{user_id}', 'sk': 'PROFILE'},
                UpdateExpression=(
                    'SET login_count = if_not_exists(login_count, :zero) + :one, '
                    'last_login_at = :now, updated_at = :now'
                ),
                ExpressionAttributeValues={':zero': 0, ':one': 1, ':now': now},
                ReturnValues='ALL_NEW',
            )
        except self.table.meta.client.exceptions.ResourceNotFoundException:
            return None
        except Exception:
            return self.get_profile(user_id)
        return self._profile_from_item(response['Attributes'])

    def record_event(
        self, user_id: str | None, event_type: str, success: bool = True, metadata: dict | None = None
    ) -> None:
        now = _now()
        event_id = str(uuid4())
        self.table.put_item(Item={
            'pk': f'USER#{user_id or "anonymous"}',
            'sk': f'EVENT#{now.isoformat()}#{event_id}',
            'id': event_id,
            'user_id': user_id,
            'event_type': event_type,
            'success': success,
            'metadata': metadata or {},
            'created_at': now.isoformat(),
            'entity_type': 'event',
            'ttl': int((now + timedelta(days=90)).timestamp()),
        })

    @staticmethod
    def _profile_from_item(item: dict[str, Any]) -> dict[str, Any]:
        return {
            'id': item.get('id') or str(item.get('pk', '')).removeprefix('USER#'),
            'email': item.get('email') or '',
            'display_name': item.get('display_name') or '',
            'status': item.get('status') or 'active',
            'is_admin': bool(item.get('is_admin')),
            'login_count': int(item.get('login_count') or 0),
            'created_at': item.get('created_at'),
            'updated_at': item.get('updated_at'),
            'last_login_at': item.get('last_login_at'),
        }


def new_request_id() -> str:
    return str(uuid4())
