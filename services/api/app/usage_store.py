from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any, Protocol

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError


class QuotaExceeded(RuntimeError):
    """A durable per-user model allowance has been exhausted."""


class UsageStore(Protocol):
    def begin_request(self, user_id: str, limits: dict[str, int]) -> dict[str, Any]: ...

    def record_tokens(self, user_id: str, input_tokens: int, output_tokens: int) -> None: ...

    def get_usage(self, user_id: str, limits: dict[str, int]) -> dict[str, Any]: ...


def _windows(now: datetime | None = None) -> tuple[tuple[str, str, datetime], tuple[str, str, datetime]]:
    now = now or datetime.now(UTC)
    tomorrow = datetime(now.year, now.month, now.day, tzinfo=UTC) + timedelta(days=1)
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        next_month = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return (
        ('daily', now.strftime('%Y-%m-%d'), tomorrow),
        ('monthly', now.strftime('%Y-%m'), next_month),
    )


def _summary(items: dict[str, dict[str, Any]], limits: dict[str, int]) -> dict[str, Any]:
    periods: dict[str, Any] = {}
    for name, key, reset in _windows():
        item = items.get(name, {})
        periods[name] = {
            'window': key,
            'requests': int(item.get('request_count', 0)),
            'request_limit': limits[f'{name}_requests'],
            'input_tokens': int(item.get('input_tokens', 0)),
            'output_tokens': int(item.get('output_tokens', 0)),
            'tokens': int(item.get('token_count', 0)),
            'token_limit': limits[f'{name}_tokens'],
            'resets_at': reset.isoformat(),
        }
    return {'daily': periods['daily'], 'monthly': periods['monthly']}


class MemoryUsageStore:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str, str], dict[str, int]] = {}
        self._lock = Lock()

    def begin_request(self, user_id: str, limits: dict[str, int]) -> dict[str, Any]:
        with self._lock:
            current = self._items(user_id)
            for name, _, _ in _windows():
                item = current[name]
                if (item.get('request_count', 0) >= limits[f'{name}_requests'] or
                        item.get('token_count', 0) >= limits[f'{name}_tokens']):
                    raise QuotaExceeded('Your model usage limit has been reached. Check Usage for the reset time.')
            for item in current.values():
                item['request_count'] = item.get('request_count', 0) + 1
            return _summary(current, limits)

    def record_tokens(self, user_id: str, input_tokens: int, output_tokens: int) -> None:
        with self._lock:
            for item in self._items(user_id).values():
                item['input_tokens'] = item.get('input_tokens', 0) + max(0, input_tokens)
                item['output_tokens'] = item.get('output_tokens', 0) + max(0, output_tokens)
                item['token_count'] = item.get('token_count', 0) + max(0, input_tokens) + max(0, output_tokens)

    def get_usage(self, user_id: str, limits: dict[str, int]) -> dict[str, Any]:
        with self._lock:
            return _summary(self._items(user_id), limits)

    def _items(self, user_id: str) -> dict[str, dict[str, int]]:
        return {
            name: self.items.setdefault((user_id, name, key), {})
            for name, key, _ in _windows()
        }


class DynamoUsageStore:
    def __init__(self, table_name: str, region: str) -> None:
        self.table_name = table_name
        self.table = boto3.resource('dynamodb', region_name=region).Table(table_name)
        self.client = boto3.client('dynamodb', region_name=region)
        self.serializer = TypeSerializer()

    def begin_request(self, user_id: str, limits: dict[str, int]) -> dict[str, Any]:
        now = datetime.now(UTC)
        transactions = []
        for name, key, _ in _windows(now):
            transactions.append({'Update': {
                'TableName': self.table_name,
                'Key': self._serialize({'pk': f'USER#{user_id}', 'sk': f'USAGE#{name.upper()}#{key}'}),
                'UpdateExpression': (
                    'SET entity_type = :type, updated_at = :updated, #window = :window, #ttl = :ttl '
                    'ADD request_count :one'
                ),
                'ConditionExpression': (
                    '(attribute_not_exists(request_count) OR request_count < :request_limit) AND '
                    '(attribute_not_exists(token_count) OR token_count < :token_limit)'
                ),
                'ExpressionAttributeNames': {'#window': 'window', '#ttl': 'ttl'},
                'ExpressionAttributeValues': self._serialize({
                    ':one': 1,
                    ':type': 'usage',
                    ':updated': now.isoformat(),
                    ':window': key,
                    ':ttl': int((now + timedelta(days=400 if name == 'monthly' else 90)).timestamp()),
                    ':request_limit': limits[f'{name}_requests'],
                    ':token_limit': limits[f'{name}_tokens'],
                }),
            }})
        try:
            self.client.transact_write_items(TransactItems=transactions)
        except ClientError as exc:
            reasons = exc.response.get('CancellationReasons', [])
            quota_failed = any(reason.get('Code') == 'ConditionalCheckFailed' for reason in reasons)
            if (exc.response.get('Error', {}).get('Code') == 'TransactionCanceledException' and
                    (quota_failed or not reasons)):
                raise QuotaExceeded(
                    'Your model usage limit has been reached. Check Usage for the reset time.'
                ) from None
            raise
        return self.get_usage(user_id, limits)

    def record_tokens(self, user_id: str, input_tokens: int, output_tokens: int) -> None:
        if input_tokens <= 0 and output_tokens <= 0:
            return
        values = {
            ':input': max(0, input_tokens),
            ':output': max(0, output_tokens),
            ':total': max(0, input_tokens) + max(0, output_tokens),
            ':updated': datetime.now(UTC).isoformat(),
        }
        transactions = []
        for name, key, _ in _windows():
            transactions.append({'Update': {
                'TableName': self.table_name,
                'Key': self._serialize({'pk': f'USER#{user_id}', 'sk': f'USAGE#{name.upper()}#{key}'}),
                'UpdateExpression': (
                    'SET updated_at = :updated '
                    'ADD input_tokens :input, output_tokens :output, token_count :total'
                ),
                'ExpressionAttributeValues': self._serialize(values),
            }})
        self.client.transact_write_items(TransactItems=transactions)

    def get_usage(self, user_id: str, limits: dict[str, int]) -> dict[str, Any]:
        items: dict[str, dict[str, Any]] = {}
        for name, key, _ in _windows():
            response = self.table.get_item(Key={
                'pk': f'USER#{user_id}', 'sk': f'USAGE#{name.upper()}#{key}',
            }, ConsistentRead=True)
            items[name] = response.get('Item', {})
        return _summary(items, limits)

    def _serialize(self, values: dict[str, Any]) -> dict[str, Any]:
        return {key: self.serializer.serialize(value) for key, value in values.items()}
