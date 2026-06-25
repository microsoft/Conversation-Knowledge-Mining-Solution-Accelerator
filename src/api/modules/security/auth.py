import base64
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from src.api.config import get_settings
from src.api.auth.auth_utils import get_authenticated_user_details
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
    """FastAPI Depends wrapper around get_authenticated_user_details().
    """
    settings = get_settings()

    # Admin API key bypass — key secrecy is the security boundary
    admin_api_key = getattr(settings, "admin_api_key", "")
    if admin_api_key:
        provided_key = request.headers.get("X-Admin-Api-Key", "")
        if provided_key == admin_api_key:
            return User(user_id="admin", name="Admin", email="", roles=["Admin"])

    # Delegate header reading + sample_user fallback to the shared GSA helper
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)

    user_id = authenticated_user.get("user_principal_id") or "anonymous"
    name = authenticated_user.get("user_name") or "Anonymous"
    principal_b64 = authenticated_user.get("client_principal_b64", "")

    # Parse email and AAD app roles from the base64 claims (only present when
    # EasyAuth is active; the sample_user placeholder value is skipped).
    email = ""
    roles: list[str] = []
    if principal_b64 and principal_b64 != "your_base_64_encoded_token":
        claims_obj = _parse_principal(principal_b64)
        for claim in claims_obj.get("claims", []):
            typ = claim.get("typ", "")
            val = claim.get("val", "")
            if typ == "name":
                name = name or val
            elif typ in ("preferred_username", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"):
                email = val
            elif typ == "roles":
                roles.append(val)

    return User(user_id=user_id, name=name, email=email, roles=roles)


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
