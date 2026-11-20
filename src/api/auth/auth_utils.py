import logging
import threading
import time
from functools import lru_cache

import httpx
import jwt
from fastapi import HTTPException

from src.api.config import Settings

logger = logging.getLogger(__name__)


class SigningKeys:
    """Cache tenant signing keys and bound refreshes, including unknown key IDs."""

    def __init__(self, tenant_id: str):
        self.url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        self._keys: dict[str, jwt.PyJWK] = {}
        self._expires_at = 0.0
        self._retry_after = 0.0
        self._lock = threading.Lock()

    def get(self, kid: str) -> jwt.PyJWK:
        with self._lock:
            now = time.monotonic()
            if now >= self._expires_at or kid not in self._keys:
                if now >= self._retry_after:
                    self._retry_after = now + 60
                    try:
                        response = httpx.get(self.url, timeout=5.0, follow_redirects=False)
                        response.raise_for_status()
                        key_set = jwt.PyJWKSet.from_dict(response.json())
                        keys = {
                            key.key_id: key for key in key_set.keys
                            if key.key_id and key.algorithm_name == "RS256"
                            and key.public_key_use in (None, "sig")
                        }
                        if not keys:
                            raise ValueError("No supported signing keys")
                    except (httpx.HTTPError, ValueError, jwt.PyJWTError) as exc:
                        logger.error("Entra signing-key refresh failed: %s", type(exc).__name__)
                        raise HTTPException(503, "Authentication service unavailable") from exc
                    self._keys = keys
                    self._expires_at = now + 3600
                elif now >= self._expires_at:
                    raise HTTPException(503, "Authentication service unavailable")
            key = self._keys.get(kid)
            if key is None:
                raise jwt.InvalidTokenError("Unknown signing key")
            return key


@lru_cache(maxsize=4)
def get_signing_keys(tenant_id: str) -> SigningKeys:
    return SigningKeys(tenant_id)


def validate_access_token(token: str, settings: Settings) -> dict:
    """Validate API access tokens; identity headers and ID tokens are not accepted."""
    header = jwt.get_unverified_header(token)
    if header.get("alg") != "RS256":
        raise jwt.InvalidTokenError("Unsupported signing algorithm")
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid or len(kid) > 256:
        raise jwt.InvalidTokenError("Missing or invalid signing key ID")
    key = get_signing_keys(settings.azure_ad_tenant_id).get(kid)
    try:
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=settings.azure_ad_client_id,
            issuer=f"https://login.microsoftonline.com/{settings.azure_ad_tenant_id}/v2.0",
            options={"require": ["exp", "nbf", "iat", "iss", "aud", "tid", "oid", "ver"]},
        )
    except (TypeError, ValueError) as exc:
        raise jwt.InvalidTokenError("Malformed token claims") from exc
    if claims["tid"] != settings.azure_ad_tenant_id or claims["ver"] != "2.0":
        raise jwt.InvalidTokenError("Invalid tenant or token version")
    if not isinstance(claims["oid"], str) or not claims["oid"]:
        raise jwt.InvalidTokenError("Missing object identity")
    # Delegated access tokens carry scp; workload access tokens carry idtyp=app.
    # An ID token can carry roles too, so roles alone cannot identify an access token.
    scopes = claims.get("scp")
    if not (isinstance(scopes, str) and "access_as_user" in scopes.split()):
        if claims.get("idtyp") != "app":
            raise jwt.InvalidTokenError("API access token required")
    roles = claims.get("roles", [])
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise jwt.InvalidTokenError("Invalid roles")
    return claims
