import logging
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientConnectionError, PyJWKClientError

from src.api.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def _get_jwks_client(tenant_id: str) -> PyJWKClient:
    return PyJWKClient(
        f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
        lifespan=300,
        timeout=10,
    )


def get_authenticated_user_details(request_headers: Mapping[str, str]) -> dict[str, Any]:
    """Validate an Entra access token; client-supplied identity headers are ignored."""
    authorization = request_headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or " " in token:
        raise HTTPException(
            status_code=401,
            detail="A Bearer access token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    tenant_id = settings.azure_ad_tenant_id
    client_id = settings.azure_ad_client_id
    if not tenant_id or not client_id:
        logger.error("Token authentication requires AZURE_AD_TENANT_ID and AZURE_AD_CLIENT_ID")
        raise HTTPException(status_code=503, detail="Authentication is not configured")

    try:
        signing_key = _get_jwks_client(tenant_id).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
            options={
                "require": ["exp", "iat", "nbf", "iss", "aud", "sub", "tid", "oid"],
                "strict_aud": True,
            },
        )
        if claims["tid"] != tenant_id or not isinstance(claims["oid"], str) or not claims["oid"]:
            raise InvalidTokenError("Invalid tenant or object identity")
        roles = claims.get("roles", [])
        if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
            raise InvalidTokenError("Invalid app roles")
        scopes = claims.get("scp", "")
        if not isinstance(scopes, str):
            raise InvalidTokenError("Invalid delegated scopes")
        # ID tokens are not API credentials, even when issued for the same app.
        delegated = "access_as_user" in scopes.split()
        application = claims.get("idtyp") == "app" and any(
            role in ("Admin", "Contributor", "Reader") for role in roles
        )
        if not delegated and not application:
            raise InvalidTokenError("An API access token is required")
        for field in ("name", "preferred_username", "email"):
            if field in claims and not isinstance(claims[field], str):
                raise InvalidTokenError(f"Invalid {field} claim")
        return claims
    except PyJWKClientConnectionError as exc:
        logger.error("Unable to retrieve Entra signing keys", exc_info=True)
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from exc
    except (InvalidTokenError, PyJWKClientError) as exc:
        logger.warning("Rejected invalid access token: %s", type(exc).__name__)
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
