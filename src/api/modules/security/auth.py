import base64
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from src.api.config import get_settings
from src.api.modules.security.models import User, UserInfo

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_principal(b64_principal: str) -> dict:
    """Decode the base64-encoded X-Ms-Client-Principal header."""
    try:
        decoded = base64.b64decode(b64_principal)
        return json.loads(decoded)
    except Exception:
        return {}


async def get_current_user(request: Request) -> User:
    """Extract user from EasyAuth headers. Falls back to dev user when not in Prod."""
    settings = get_settings()
    is_prod = getattr(settings, "app_env", "").lower() in ("prod", "production")

    # Read EasyAuth headers
    principal_id = request.headers.get("X-Ms-Client-Principal-Id", "")
    principal_name = request.headers.get("X-Ms-Client-Principal-Name", "")
    principal_b64 = request.headers.get("X-Ms-Client-Principal", "")

    if principal_id and principal_id != "default":
        # EasyAuth is active — extract user details
        name = principal_name or ""
        email = ""
        roles: list[str] = []

        if principal_b64:
            claims = _parse_principal(principal_b64)
            for claim in claims.get("claims", []):
                if claim.get("typ") == "name":
                    name = name or claim.get("val", "")
                elif claim.get("typ") in ("preferred_username", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"):
                    email = claim.get("val", "")
                elif claim.get("typ") == "roles":
                    roles.append(claim.get("val", ""))

        return User(user_id=principal_id, name=name, email=email, roles=roles)

    # No EasyAuth headers.
    # In production, fail closed unless explicitly allowed for break-glass operations.
    if is_prod and not getattr(settings, "auth_allow_anonymous_in_prod", False):
        raise HTTPException(status_code=401, detail="Authentication required")

    if is_prod:
        logger.warning("No EasyAuth headers in prod — anonymous mode explicitly enabled")
        return User(user_id="anonymous", name="User", email="", roles=["Reader"])

    return User(user_id="anonymous", name="User", email="", roles=["Admin"])


def require_role(required_role: str):
    """Dependency factory to enforce role-based access."""

    async def role_checker(user: User = Depends(get_current_user)) -> User:
        role_hierarchy = {"reader": 0, "contributor": 1, "admin": 2}
        user_level = role_hierarchy.get(user.best_role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        if user_level < required_level:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return role_checker


@router.get("/me", response_model=UserInfo)
async def get_me(user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return UserInfo(user_id=user.user_id, name=user.name, email=user.email, roles=user.roles)
