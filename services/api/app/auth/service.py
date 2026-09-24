from __future__ import annotations

from typing import Any

from app.auth.store import DynamoUserStore, MemoryUserStore, UserStore
from app.config import Settings


def _claim_email(claims: dict[str, Any]) -> str:
    return str(claims.get('email') or claims.get('cognito:username') or '').lower()


def _claim_name(claims: dict[str, Any], fallback: str = '') -> str:
    return str(
        fallback
        or claims.get('name')
        or claims.get('given_name')
        or ''
    ).strip()


class AuthService:
    def __init__(self, settings: Settings, store: UserStore | None = None) -> None:
        self.settings = settings
        if store is not None:
            self.store = store
        elif settings.auth_profiles_table.strip():
            self.store = DynamoUserStore(settings.auth_profiles_table, settings.cognito_pool_region)
        else:
            self.store = MemoryUserStore()

    def sync_user(self, claims: dict[str, Any], *, event: str, display_name: str = '') -> dict[str, Any]:
        user_id = str(claims['sub'])
        email = _claim_email(claims)
        name = _claim_name(claims, display_name)
        is_admin = email in self.settings.admin_email_set
        profile = self.store.upsert_profile(
            user_id, email=email or f'{user_id}@unknown', display_name=name, is_admin=is_admin
        )
        if profile.get('status') == 'disabled':
            self.store.record_event(user_id, event, success=False, metadata={'reason': 'disabled'})
            raise PermissionError('Account disabled')
        if event == 'login':
            profile = self.store.record_login(user_id) or profile
        self.store.record_event(user_id, event, success=True, metadata={'provider': 'cognito'})
        return profile

    def me(self, claims: dict[str, Any]) -> dict[str, Any]:
        user_id = str(claims['sub'])
        profile = self.store.get_profile(user_id)
        if profile:
            return profile
        email = _claim_email(claims)
        return self.store.upsert_profile(
            user_id,
            email=email or f'{user_id}@unknown',
            display_name=_claim_name(claims),
            is_admin=email in self.settings.admin_email_set,
        )
