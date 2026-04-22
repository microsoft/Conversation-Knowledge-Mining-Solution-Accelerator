from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.config import get_settings
from backend.modules.security.models import User, UserInfo

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)

# Cache for AAD JWKS keys
_jwks_cache: dict = {}


def _get_jwks(tenant_id: str) -> dict:
    """Fetch and cache Microsoft Entra ID signing keys."""
    if _jwks_cache.get(tenant_id):
        return _jwks_cache[tenant_id]

    openid_url = f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration"
    with httpx.Client(timeout=10) as client:
        config = client.get(openid_url).json()
        jwks = client.get(config["jwks_uri"]).json()
    _jwks_cache[tenant_id] = jwks
    return jwks


def _decode_aad_token(token: str) -> dict:
    """Validate and decode a Microsoft Entra ID access token."""
    settings = get_settings()
    tenant_id = settings.azure_ad_tenant_id
    client_id = settings.azure_ad_client_id

    # Get the key id from the token header
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    if not kid:
        raise JWTError("Token header missing 'kid'")

    # Find the matching signing key
    jwks = _get_jwks(tenant_id)
    rsa_key = {}
    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"],
            }
            break

    if not rsa_key:
        # Refresh JWKS cache and retry (key rotation)
        _jwks_cache.pop(tenant_id, None)
        jwks = _get_jwks(tenant_id)
        for key in jwks.get("keys", []):
            if key["kid"] == kid:
                rsa_key = {"kty": key["kty"], "kid": key["kid"], "use": key["use"], "n": key["n"], "e": key["e"]}
                break
        if not rsa_key:
            raise JWTError("Unable to find matching signing key")

    payload = jwt.decode(
        token,
        rsa_key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        options={"verify_at_hash": False},
    )
    return payload


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> User:
    """Validate the AAD bearer token. Falls back to dev user if AAD is not configured."""
    settings = get_settings()

    # Dev mode: if AAD is not configured, allow unauthenticated access
    aad_configured = (
        settings.azure_ad_tenant_id
        and settings.azure_ad_client_id
        and not settings.azure_ad_tenant_id.startswith("<")
        and not settings.azure_ad_client_id.startswith("<")
    )
    if not aad_configured:
        return User(user_id="dev-user", name="Developer", email="dev@local", roles=["Admin"])

    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        claims = _decode_aad_token(credentials.credentials)
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {e}")

    return User(
        user_id=claims.get("oid", claims.get("sub", "")),
        name=claims.get("name", ""),
        email=claims.get("preferred_username", claims.get("email", "")),
        roles=claims.get("roles", []),
    )


def require_role(required_role: str):
    """Dependency factory to enforce role-based access via AAD app roles."""

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
