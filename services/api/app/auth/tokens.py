from __future__ import annotations

from functools import lru_cache
from typing import Any

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient, PyJWTError


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_keys=True)


def verify_cognito_token(
    token: str,
    *,
    region: str,
    user_pool_id: str,
    client_id: str,
) -> dict[str, Any]:
    """Verify a Cognito ID token (RS256 via JWKS)."""
    if not token or not user_pool_id or not client_id:
        raise HTTPException(401, detail={'code': 'unauthorized', 'message': 'Sign in required.'})
    issuer = f'https://cognito-idp.{region}.amazonaws.com/{user_pool_id}'
    jwks_url = f'{issuer}/.well-known/jwks.json'
    try:
        key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=['RS256'],
            audience=client_id,
            issuer=issuer,
            options={'require': ['exp', 'sub', 'token_use']},
        )
    except PyJWTError as exc:
        raise HTTPException(
            401, detail={'code': 'unauthorized', 'message': 'Session expired. Sign in again.'}
        ) from exc
    if claims.get('token_use') != 'id':
        raise HTTPException(401, detail={'code': 'unauthorized', 'message': 'Sign in required.'})
    if not claims.get('sub'):
        raise HTTPException(401, detail={'code': 'unauthorized', 'message': 'Sign in required.'})
    return claims


def verify_dev_token(token: str, *, jwt_secret: str, audience: str = 'adda-ai') -> dict[str, Any]:
    """HS256 helper for local/unit tests only. Never use in production."""
    if not token or not jwt_secret:
        raise HTTPException(401, detail={'code': 'unauthorized', 'message': 'Sign in required.'})
    try:
        claims = jwt.decode(
            token,
            jwt_secret,
            algorithms=['HS256'],
            audience=audience,
            options={'require': ['exp', 'sub']},
        )
    except PyJWTError as exc:
        raise HTTPException(
            401, detail={'code': 'unauthorized', 'message': 'Session expired. Sign in again.'}
        ) from exc
    if not claims.get('sub'):
        raise HTTPException(401, detail={'code': 'unauthorized', 'message': 'Sign in required.'})
    return claims


def verify_bearer_token(
    token: str,
    *,
    region: str = '',
    user_pool_id: str = '',
    client_id: str = '',
    dev_jwt_secret: str = '',
) -> dict[str, Any]:
    if user_pool_id and client_id:
        return verify_cognito_token(
            token, region=region or 'ap-south-1', user_pool_id=user_pool_id, client_id=client_id
        )
    if dev_jwt_secret:
        return verify_dev_token(token, jwt_secret=dev_jwt_secret)
    raise HTTPException(
        503,
        detail={'code': 'auth_not_configured', 'message': 'Authentication is not configured on this API yet.'},
    )
