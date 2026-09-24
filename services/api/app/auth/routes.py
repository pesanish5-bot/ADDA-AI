from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from app.auth.models import Profile, SyncBody
from app.auth.service import AuthService
from app.auth.tokens import verify_bearer_token
from app.config import Settings


def create_auth_router(settings: Settings, auth: AuthService) -> APIRouter:
    router = APIRouter(prefix='/api/auth', tags=['auth'])

    def bearer_claims(authorization: str | None = Header(default=None)) -> dict:
        if not settings.auth_configured:
            raise HTTPException(503, detail={
                'code': 'auth_not_configured',
                'message': 'Authentication is not configured on this API yet.',
            })
        scheme, _, token = (authorization or '').partition(' ')
        if scheme.lower() != 'bearer' or not token:
            raise HTTPException(401, detail={'code': 'unauthorized', 'message': 'Sign in required.'})
        return verify_bearer_token(
            token,
            region=settings.cognito_pool_region,
            user_pool_id=settings.cognito_user_pool_id,
            client_id=settings.cognito_client_id,
            dev_jwt_secret=settings.auth_dev_jwt_secret,
        )

    @router.get('/status')
    def status():
        return {
            'configured': settings.auth_configured,
            'provider': 'cognito' if settings.cognito_configured else ('dev' if settings.auth_dev_jwt_secret else 'none'),
            'auth_required': settings.api_requires_auth,
        }

    @router.get('/me', response_model=Profile)
    def me(claims: dict = Depends(bearer_claims)):
        return auth.me(claims)

    @router.post('/sync', response_model=Profile)
    def sync(body: SyncBody, claims: dict = Depends(bearer_claims)):
        try:
            return auth.sync_user(claims, event=body.event, display_name=body.display_name)
        except PermissionError:
            raise HTTPException(403, detail={'code': 'forbidden', 'message': 'This account is disabled.'})

    return router


def optional_user_id(settings: Settings, authorization: str | None) -> str | None:
    if not settings.auth_configured or not authorization:
        return None
    scheme, _, token = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not token:
        return None
    try:
        claims = verify_bearer_token(
            token,
            region=settings.cognito_pool_region,
            user_pool_id=settings.cognito_user_pool_id,
            client_id=settings.cognito_client_id,
            dev_jwt_secret=settings.auth_dev_jwt_secret,
        )
        return str(claims.get('sub') or '') or None
    except HTTPException:
        return None
