from __future__ import annotations

import json
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.billing import BillingError


@dataclass(frozen=True)
class BillingSecrets:
    secret_key: str
    webhook_secret: str


class BillingSecretProvider(Protocol):
    def get(self) -> BillingSecrets: ...


def _validated(payload: Any) -> BillingSecrets:
    if not isinstance(payload, dict):
        raise BillingError(
            'Billing credentials are unavailable.', 'billing_credentials_unavailable', 503
        )
    secret_key = str(payload.get('secret_key') or '').strip()
    webhook_secret = str(payload.get('webhook_secret') or '').strip()
    if not secret_key.startswith(('sk_', 'rk_')) or not webhook_secret.startswith('whsec_'):
        raise BillingError(
            'Billing credentials are unavailable.', 'billing_credentials_unavailable', 503
        )
    return BillingSecrets(secret_key=secret_key, webhook_secret=webhook_secret)


class StaticBillingSecretProvider:
    """Development-only provider; deployed environments reject inline secrets."""

    def __init__(self, secret_key: str, webhook_secret: str) -> None:
        self.secrets = _validated({
            'secret_key': secret_key,
            'webhook_secret': webhook_secret,
        })

    def get(self) -> BillingSecrets:
        return self.secrets


class AwsBillingSecretProvider:
    """Fetch and briefly cache Stripe credentials without placing them in Lambda config."""

    def __init__(
        self, secret_arn: str, region: str, *, client: Any | None = None, cache_seconds: int = 300
    ) -> None:
        self.secret_arn = secret_arn
        self.client = client or boto3.client('secretsmanager', region_name=region)
        self.cache_seconds = cache_seconds
        self._cached: BillingSecrets | None = None
        self._expires_at = 0.0
        self._lock = Lock()

    def get(self) -> BillingSecrets:
        now = time.monotonic()
        if self._cached and now < self._expires_at:
            return self._cached
        with self._lock:
            now = time.monotonic()
            if self._cached and now < self._expires_at:
                return self._cached
            try:
                response = self.client.get_secret_value(SecretId=self.secret_arn)
                payload = json.loads(str(response.get('SecretString') or ''))
                secrets = _validated(payload)
            except (BotoCoreError, ClientError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise BillingError(
                    'Billing credentials are unavailable.',
                    'billing_credentials_unavailable',
                    503,
                ) from exc
            self._cached = secrets
            self._expires_at = now + self.cache_seconds
            return secrets
