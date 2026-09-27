from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Profile(BaseModel):
    id: str
    email: str
    display_name: str = ''
    status: str = 'active'
    is_admin: bool = False
    login_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None


class AuthEvent(BaseModel):
    id: int | None = None
    user_id: str | None = None
    event_type: str
    success: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class SyncBody(BaseModel):
    event: str = Field(default='login', max_length=40)
    display_name: str = Field(default='', max_length=80)

    @field_validator('event')
    @classmethod
    def valid_event(cls, value: str) -> str:
        allowed = {'login', 'register', 'refresh', 'logout', 'verify', 'password_reset'}
        event = value.strip().lower()
        if event not in allowed:
            raise ValueError('Unsupported auth event.')
        return event

    @field_validator('display_name')
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()[:80]
