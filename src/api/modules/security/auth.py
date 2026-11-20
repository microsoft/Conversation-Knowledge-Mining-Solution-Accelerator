import hmac
import logging

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from src.api.auth.auth_utils import validate_access_token
from src.api.config import get_settings
from src.api.modules.security.models import User, UserInfo

logger = logging.getLogger(__name__)
router = APIRouter()
_ROLE_HIERARCHY = {"reader": 0, "contributor": 1, "admin": 2}


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Valid API authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(request: Request) -> User:
    settings = get_settings()
    provided_key = request.headers.get("X-Admin-Api-Key")
    if provided_key is not None:
        if (
            settings.app_env.lower() in ("development", "local")
            and settings.admin_api_key
            and hmac.compare_digest(provided_key.encode(), settings.admin_api_key.encode())
        ):
            return User(user_id="local-admin", name="Local administrator", roles=["Admin"])
        logger.warning("Rejected invalid or disabled development API key")
        raise _unauthorized()

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 32768:
        raise _unauthorized()
    if not settings.azure_ad_tenant_id or not settings.azure_ad_client_id:
        logger.error("Entra authentication requested without tenant/client configuration")
        raise HTTPException(503, "Authentication is not configured")
    try:
        claims = await run_in_threadpool(validate_access_token, token, settings)
    except jwt.PyJWTError as exc:
        logger.warning("Rejected API access token: %s", type(exc).__name__)
        raise _unauthorized() from exc
    return User(
        user_id=claims["oid"],
        name=claims.get("name", "") if isinstance(claims.get("name", ""), str) else "",
        email=claims.get("preferred_username", "")
        if isinstance(claims.get("preferred_username", ""), str) else "",
        roles=claims.get("roles", []),
    )


def require_role(required_role: str):
    """Enforce explicit app roles; unassigned users have no application access."""
    if required_role not in _ROLE_HIERARCHY:
        raise ValueError(f"Unknown required role: {required_role}")

    async def role_checker(user: User = Depends(get_current_user)) -> User:
        role = user.best_role
        if role is None or _ROLE_HIERARCHY[role] < _ROLE_HIERARCHY[required_role]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return role_checker


@router.get("/me", response_model=UserInfo)
async def get_me(user: User = Depends(get_current_user)):
    return UserInfo(user_id=user.user_id, name=user.name, email=user.email, roles=user.roles)
