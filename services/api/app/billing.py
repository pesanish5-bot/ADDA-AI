from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Protocol
from urllib.parse import urljoin

import boto3
import httpx

ACTIVE_STATUSES = {'active', 'trialing'}


class BillingError(RuntimeError):
    def __init__(self, message: str, code: str = 'billing_error', status: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


class BillingStore(Protocol):
    def get(self, user_id: str) -> dict[str, Any]: ...

    def update(self, user_id: str, values: dict[str, Any]) -> dict[str, Any]: ...

    def user_for_customer(self, customer_id: str) -> str | None: ...

    def event_processed(self, event_id: str) -> bool: ...

    def mark_event_processed(self, event_id: str, event_type: str) -> None: ...


class BillingGateway(Protocol):
    def create_checkout(self, user_id: str, email: str, customer_id: str = '') -> str: ...

    def create_portal(self, customer_id: str) -> str: ...

    def list_invoices(self, customer_id: str) -> list[dict[str, Any]]: ...

    def get_pro_offer(self) -> dict[str, Any]: ...


def _default_billing(user_id: str) -> dict[str, Any]:
    return {
        'user_id': user_id,
        'plan': 'free',
        'status': 'free',
        'customer_id': '',
        'subscription_id': '',
        'price_id': '',
        'current_period_end': None,
        'cancel_at_period_end': False,
        'updated_at': None,
    }


class MemoryBillingStore:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self.customers: dict[str, str] = {}
        self.events: set[str] = set()
        self._lock = Lock()

    def get(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            return dict(self.records.get(user_id, _default_billing(user_id)))

    def update(self, user_id: str, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            record = dict(self.records.get(user_id, _default_billing(user_id)))
            record.update(values)
            record['updated_at'] = datetime.now(UTC).isoformat()
            self.records[user_id] = record
            customer_id = str(record.get('customer_id') or '')
            if customer_id:
                self.customers[customer_id] = user_id
            return dict(record)

    def user_for_customer(self, customer_id: str) -> str | None:
        with self._lock:
            return self.customers.get(customer_id)

    def event_processed(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self.events

    def mark_event_processed(self, event_id: str, _event_type: str) -> None:
        with self._lock:
            self.events.add(event_id)


class DynamoBillingStore:
    def __init__(self, table_name: str, region: str) -> None:
        self.table = boto3.resource('dynamodb', region_name=region).Table(table_name)

    def get(self, user_id: str) -> dict[str, Any]:
        response = self.table.get_item(Key={'pk': f'USER#{user_id}', 'sk': 'BILLING'})
        item = response.get('Item')
        if not item:
            return _default_billing(user_id)
        return {**_default_billing(user_id), **{
            key: value for key, value in item.items() if key not in {'pk', 'sk', 'entity_type'}
        }}

    def update(self, user_id: str, values: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        record = {**self.get(user_id), **values, 'user_id': user_id, 'updated_at': now}
        item = {
            'pk': f'USER#{user_id}', 'sk': 'BILLING', 'entity_type': 'billing', **record,
        }
        # DynamoDB does not accept None values in expression updates consistently across tools.
        self.table.put_item(Item={key: value for key, value in item.items() if value is not None})
        customer_id = str(record.get('customer_id') or '')
        if customer_id:
            self.table.put_item(Item={
                'pk': f'BILLING#CUSTOMER#{customer_id}', 'sk': 'OWNER',
                'entity_type': 'billing_customer', 'user_id': user_id, 'updated_at': now,
            })
        return record

    def user_for_customer(self, customer_id: str) -> str | None:
        response = self.table.get_item(
            Key={'pk': f'BILLING#CUSTOMER#{customer_id}', 'sk': 'OWNER'}
        )
        item = response.get('Item')
        return str(item.get('user_id') or '') or None if item else None

    def event_processed(self, event_id: str) -> bool:
        response = self.table.get_item(
            Key={'pk': f'BILLING#EVENT#{event_id}', 'sk': 'PROCESSED'},
            ProjectionExpression='pk',
        )
        return bool(response.get('Item'))

    def mark_event_processed(self, event_id: str, event_type: str) -> None:
        self.table.put_item(
            Item={
                'pk': f'BILLING#EVENT#{event_id}', 'sk': 'PROCESSED',
                'entity_type': 'billing_event', 'event_type': event_type,
                'processed_at': datetime.now(UTC).isoformat(),
            },
            ConditionExpression='attribute_not_exists(pk)',
        )


class StripeGateway:
    """Small server-side Stripe REST client; secret keys never reach the browser."""

    def __init__(self, secret_key: str, frontend_origin: str, pro_price_id: str) -> None:
        self.secret_key = secret_key
        self.frontend_origin = frontend_origin.rstrip('/') + '/'
        self.pro_price_id = pro_price_id

    def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                f'https://api.stripe.com/v1/{path}',
                data=data,
                auth=(self.secret_key, ''),
                timeout=12,
            )
        except httpx.HTTPError as exc:
            raise BillingError('Billing provider is temporarily unavailable.') from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise BillingError('Billing provider returned an invalid response.') from exc
        if response.is_error:
            message = payload.get('error', {}).get('message')
            raise BillingError(str(message or 'Billing provider rejected the request.'))
        return payload

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.get(
                f'https://api.stripe.com/v1/{path}',
                params=params,
                auth=(self.secret_key, ''),
                timeout=12,
            )
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BillingError('Billing provider is temporarily unavailable.') from exc
        if response.is_error:
            raise BillingError('Billing provider rejected the request.')
        return payload

    def create_checkout(
        self, user_id: str, email: str, customer_id: str = ''
    ) -> str:
        data: dict[str, Any] = {
            'mode': 'subscription',
            'line_items[0][price]': self.pro_price_id,
            'line_items[0][quantity]': 1,
            'client_reference_id': user_id,
            'metadata[adda_user_id]': user_id,
            'subscription_data[metadata][adda_user_id]': user_id,
            'success_url': urljoin(self.frontend_origin, 'settings/?billing=success'),
            'cancel_url': urljoin(self.frontend_origin, 'settings/?billing=cancelled'),
            'allow_promotion_codes': 'true',
        }
        if customer_id:
            data['customer'] = customer_id
        else:
            data['customer_email'] = email
        session = self._post('checkout/sessions', data)
        url = str(session.get('url') or '')
        if not url.startswith('https://checkout.stripe.com/'):
            raise BillingError('Stripe did not return a safe Checkout URL.')
        return url

    def create_portal(self, customer_id: str) -> str:
        session = self._post('billing_portal/sessions', {
            'customer': customer_id,
            'return_url': urljoin(self.frontend_origin, 'settings/'),
        })
        url = str(session.get('url') or '')
        if not url.startswith('https://billing.stripe.com/'):
            raise BillingError('Stripe did not return a safe billing portal URL.')
        return url

    def list_invoices(self, customer_id: str) -> list[dict[str, Any]]:
        payload = self._get('invoices', {'customer': customer_id, 'limit': 12})
        invoices = []
        for item in payload.get('data') or []:
            invoices.append({
                'id': str(item.get('id') or ''),
                'number': item.get('number'),
                'status': str(item.get('status') or 'unknown'),
                'currency': str(item.get('currency') or 'usd'),
                'amount_due': int(item.get('amount_due') or 0),
                'amount_paid': int(item.get('amount_paid') or 0),
                'created': int(item.get('created') or 0),
                'hosted_invoice_url': _safe_stripe_url(item.get('hosted_invoice_url')),
                'invoice_pdf': _safe_stripe_url(item.get('invoice_pdf')),
            })
        return invoices

    def get_pro_offer(self) -> dict[str, Any]:
        price = self._get(f'prices/{self.pro_price_id}', {})
        recurring = price.get('recurring') or {}
        return {
            'amount': int(price.get('unit_amount') or 0),
            'currency': str(price.get('currency') or 'usd'),
            'interval': str(recurring.get('interval') or 'month'),
        }


def _safe_stripe_url(value: Any) -> str | None:
    url = str(value or '')
    return url if url.startswith('https://') else None


def verify_stripe_event(payload: bytes, signature: str, secret: str, tolerance: int = 300) -> dict:
    fields: dict[str, list[str]] = {}
    for part in signature.split(','):
        key, separator, value = part.partition('=')
        if separator:
            fields.setdefault(key, []).append(value)
    try:
        timestamp = int(fields['t'][0])
    except (KeyError, ValueError, IndexError) as exc:
        raise BillingError('Invalid Stripe signature.', 'invalid_webhook', 400) from exc
    if abs(int(time.time()) - timestamp) > tolerance:
        raise BillingError('Expired Stripe signature.', 'invalid_webhook', 400)
    signed = f'{timestamp}.'.encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in fields.get('v1', [])):
        raise BillingError('Invalid Stripe signature.', 'invalid_webhook', 400)
    try:
        event = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise BillingError('Invalid webhook payload.', 'invalid_webhook', 400) from exc
    if not isinstance(event, dict) or not event.get('id') or not event.get('type'):
        raise BillingError('Invalid webhook event.', 'invalid_webhook', 400)
    return event


def _subscription_price(obj: dict[str, Any]) -> str:
    items = ((obj.get('items') or {}).get('data') or [])
    if not items:
        return ''
    return str(((items[0].get('price') or {}).get('id')) or '')


def process_stripe_event(
    event: dict[str, Any], store: BillingStore, pro_price_id: str
) -> bool:
    event_id = str(event['id'])
    event_type = str(event['type'])
    if store.event_processed(event_id):
        return False
    obj = ((event.get('data') or {}).get('object') or {})
    if not isinstance(obj, dict):
        raise BillingError('Invalid webhook object.', 'invalid_webhook', 400)

    user_id = ''
    values: dict[str, Any] = {}
    if event_type == 'checkout.session.completed':
        user_id = str(obj.get('client_reference_id') or (obj.get('metadata') or {}).get('adda_user_id') or '')
        values = {
            'customer_id': str(obj.get('customer') or ''),
            'subscription_id': str(obj.get('subscription') or ''),
            'status': 'active' if obj.get('payment_status') in {'paid', 'no_payment_required'} else 'incomplete',
            'price_id': pro_price_id,
        }
    elif event_type.startswith('customer.subscription.'):
        customer_id = str(obj.get('customer') or '')
        user_id = str((obj.get('metadata') or {}).get('adda_user_id') or '')
        user_id = user_id or (store.user_for_customer(customer_id) if customer_id else '') or ''
        status = 'canceled' if event_type == 'customer.subscription.deleted' else str(obj.get('status') or 'incomplete')
        values = {
            'customer_id': customer_id,
            'subscription_id': str(obj.get('id') or ''),
            'status': status,
            'price_id': _subscription_price(obj),
            'current_period_end': obj.get('current_period_end'),
            'cancel_at_period_end': bool(obj.get('cancel_at_period_end')),
        }
    elif event_type in {'invoice.paid', 'invoice.payment_failed'}:
        customer_id = str(obj.get('customer') or '')
        user_id = (store.user_for_customer(customer_id) if customer_id else '') or ''
        if user_id:
            values = {'status': 'active' if event_type == 'invoice.paid' else 'past_due'}

    if user_id and values:
        entitled = values.get('status') in ACTIVE_STATUSES and values.get(
            'price_id', store.get(user_id).get('price_id')
        ) == pro_price_id
        values['plan'] = 'pro' if entitled else 'free'
        store.update(user_id, values)
    store.mark_event_processed(event_id, event_type)
    return True


def billing_summary(
    record: dict[str, Any], configured: bool, pro_price_id: str,
    free_limits: dict[str, int], pro_limits: dict[str, int], invoices: list[dict] | None = None,
    pro_offer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pro = record.get('status') in ACTIVE_STATUSES and record.get('price_id') == pro_price_id
    return {
        'configured': configured,
        'plan': 'pro' if pro else 'free',
        'status': record.get('status') or 'free',
        'has_customer': bool(record.get('customer_id')),
        'current_period_end': record.get('current_period_end'),
        'cancel_at_period_end': bool(record.get('cancel_at_period_end')),
        'entitlements': pro_limits if pro else free_limits,
        'invoices': invoices or [],
        'pro_offer': pro_offer,
    }
