import hmac

from fastapi import APIRouter, Depends, HTTPException, Request
from src.api.config import get_settings
from src.api.auth.auth_utils import get_authenticated_user_details
from src.api.modules.security.models import User, UserInfo

router = APIRouter()


def get_current_user(request: Request) -> User:
    """Resolve identity only from a validated access token or configured script key."""
    cached_user = getattr(request.state, "user", None)
    if isinstance(cached_user, User):
        return cached_user
    settings = get_settings()

    provided_key = request.headers.get("X-Admin-Api-Key")
    if provided_key is not None:
        if not settings.admin_api_key or not hmac.compare_digest(
            provided_key.encode("utf-8"), settings.admin_api_key.encode("utf-8")
        ):
            raise HTTPException(status_code=401, detail="Invalid admin API key")
        user = User(user_id="admin", name="Admin", roles=["Admin"])
    else:
        claims = get_authenticated_user_details(request.headers)
        user = User(
            user_id=claims["oid"],
            name=claims.get("name", ""),
            email=claims.get("preferred_username") or claims.get("email", ""),
            roles=claims.get("roles", []),
        )
    request.state.user = user
    return user


def authenticate_request(request: Request) -> None:
    """Require authentication by default, excluding only liveness/health checks."""
    if request.method in ("GET", "HEAD") and request.url.path in ("/", "/api/health"):
        return
    get_current_user(request)


def require_role(required_role: str):
    """Dependency factory to enforce role-based access."""
    role_hierarchy = {"reader": 0, "contributor": 1, "admin": 2}
    if required_role not in role_hierarchy:
        raise ValueError(f"Unknown required role: {required_role}")

    async def role_checker(user: User = Depends(get_current_user)) -> User:
        user_level = role_hierarchy[user.best_role]
        required_level = role_hierarchy[required_role]
        if user_level < required_level:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return role_checker


@router.get("/me", response_model=UserInfo)
async def get_me(user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return UserInfo(user_id=user.user_id, name=user.name, email=user.email, roles=user.roles)
