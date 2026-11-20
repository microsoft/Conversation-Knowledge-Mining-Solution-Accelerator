import base64
import json
import time
from unittest.mock import Mock

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api import config
from src.api.auth import auth_utils
from src.api.config import Settings
from src.api.modules.security import auth
from src.api.modules.security.models import User

TENANT = "11111111-1111-4111-8111-111111111111"
CLIENT = "22222222-2222-4222-8222-222222222222"
USER = "33333333-3333-4333-8333-333333333333"


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def security(monkeypatch, signing_key):
    settings = Settings(
        _env_file=None,
        app_env="local",
        azure_ad_tenant_id=TENANT,
        azure_ad_client_id=CLIENT,
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    auth_utils.get_signing_keys.cache_clear()
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))
    jwk.update(kid="test-key", alg="RS256", use="sig")
    fetch = Mock(return_value=httpx.Response(
        200, json={"keys": [jwk]}, request=httpx.Request("GET", "https://example.test/keys"),
    ))
    monkeypatch.setattr(auth_utils.httpx, "get", fetch)
    yield settings, fetch
    auth_utils.get_signing_keys.cache_clear()


def token(signing_key, assigned_roles=None, **overrides):
    now = int(time.time())
    claims = {
        "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "aud": CLIENT,
        "tid": TENANT,
        "oid": USER,
        "ver": "2.0",
        "iat": now,
        "nbf": now - 1,
        "exp": now + 300,
        "scp": "access_as_user",
        "roles": ["Reader"] if assigned_roles is None else assigned_roles,
    }
    claims.update(overrides)
    return jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "test-key"})


@pytest.fixture
def client(security):
    app = FastAPI()
    calls = Mock()

    @app.get("/reader")
    async def read(user=Depends(auth.require_role("reader"))):
        calls.read()
        return {"user_id": user.user_id, "role": user.best_role}

    @app.post("/contributor")
    async def write(user=Depends(auth.require_role("contributor"))):
        calls.write()
        return {"role": user.best_role}

    @app.delete("/admin")
    async def clear(user=Depends(auth.require_role("admin"))):
        calls.clear()
        return {"role": user.best_role}

    return TestClient(app), calls


@pytest.mark.parametrize("headers", [
    {},
    {"X-Ms-Client-Principal-Id": "attacker"},
    {
        "X-Ms-Client-Principal-Id": "attacker",
        "X-Ms-Client-Principal": base64.b64encode(json.dumps({
            "claims": [{"typ": "roles", "val": "Admin"}],
        }).encode()).decode(),
    },
    {"Authorization": "Basic not-a-token"},
    {"Authorization": "Bearer "},
    {"X-Admin-Api-Key": "wrong"},
])
def test_missing_or_forged_identity_is_unauthorized(client, headers):
    api, calls = client
    for method, path in (("get", "/reader"), ("post", "/contributor"), ("delete", "/admin")):
        response = getattr(api, method)(path, headers=headers)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
    assert calls.mock_calls == []


@pytest.mark.parametrize(("roles", "expected"), [
    ([], [403, 403, 403]),
    (["Unknown"], [403, 403, 403]),
    (["Reader"], [200, 403, 403]),
    (["Contributor"], [200, 200, 403]),
    (["Admin"], [200, 200, 200]),
    (["Reader", "Admin"], [200, 200, 200]),
])
def test_explicit_role_hierarchy(client, signing_key, roles, expected):
    api, calls = client
    headers = {"Authorization": f"Bearer {token(signing_key, roles)}"}
    responses = [
        api.get("/reader", headers=headers),
        api.post("/contributor", headers=headers),
        api.delete("/admin", headers=headers),
    ]
    assert [response.status_code for response in responses] == expected
    assert len(calls.mock_calls) == expected.count(200)
    if expected[0] == 200:
        assert responses[0].json()["user_id"] == USER


@pytest.mark.parametrize("overrides", [
    {"exp": 1},
    {"nbf": int(time.time()) + 3600},
    {"iat": int(time.time()) + 3600},
    {"exp": {}},
    {"nbf": []},
    {"iat": {}},
    {"iss": "https://attacker.test"},
    {"aud": "another-api"},
    {"tid": "another-tenant"},
    {"ver": "1.0"},
    {"oid": ""},
    {"oid": 123},
    {"roles": "Admin"},
    {"roles": [123]},
    {"scp": ""},
    {"scp": "User.Read"},
])
def test_invalid_token_claims_fail_closed(client, signing_key, overrides):
    api, calls = client
    response = api.delete("/admin", headers={
        "Authorization": f"Bearer {token(signing_key, ['Admin'], **overrides)}",
    })
    assert response.status_code == 401
    calls.clear.assert_not_called()


def test_workload_access_token(client, signing_key):
    api, _ = client
    response = api.post("/contributor", headers={
        "Authorization": f"Bearer {token(signing_key, ['Contributor'], scp=None, idtyp='app')}",
    })
    assert response.status_code == 200


@pytest.mark.parametrize("claim", ["exp", "nbf", "iat", "iss", "aud", "tid", "oid", "ver"])
def test_missing_required_claim(client, signing_key, claim):
    claims = jwt.decode(token(signing_key), options={"verify_signature": False})
    del claims[claim]
    raw_token = jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "test-key"})
    api, _ = client
    assert api.get("/reader", headers={"Authorization": f"Bearer {raw_token}"}).status_code == 401


def test_forged_headers_cannot_override_valid_identity(client, signing_key):
    api, _ = client
    response = api.get("/reader", headers={
        "Authorization": f"Bearer {token(signing_key)}",
        "X-Ms-Client-Principal-Id": "attacker",
        "X-Ms-Client-Principal": "malformed",
    })
    assert response.status_code == 200
    assert response.json()["user_id"] == USER
    assert api.delete("/admin", headers={
        "Authorization": f"Bearer {token(signing_key)}",
        "X-Ms-Client-Principal": base64.b64encode(b'{"roles":["Admin"]}').decode(),
    }).status_code == 403


def test_tampered_signature(client, signing_key):
    api, calls = client
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert api.delete("/admin", headers={
        "Authorization": f"Bearer {token(other_key, ['Admin'])}",
    }).status_code == 401
    calls.clear.assert_not_called()


@pytest.mark.parametrize("raw_token", [
    "not-a-jwt",
    jwt.encode({"roles": ["Admin"]}, key="", algorithm="none"),
    jwt.encode({"roles": ["Admin"]}, key="untrusted-test-key", algorithm="HS256"),
])
def test_bad_token_format_or_algorithm(client, raw_token):
    api, _ = client
    assert api.get("/reader", headers={"Authorization": f"Bearer {raw_token}"}).status_code == 401


def test_signing_keys_are_cached_and_unknown_kids_are_throttled(security):
    _, fetch = security
    keys = auth_utils.get_signing_keys(TENANT)
    assert keys.get("test-key").key_id == "test-key"
    for index in range(10):
        with pytest.raises(jwt.InvalidTokenError):
            keys.get(f"attacker-{index}")
    assert keys.get("test-key").key_id == "test-key"
    assert fetch.call_count == 1


def test_signing_key_outage_returns_503_without_fallback(client, signing_key, security):
    _, fetch = security
    fetch.side_effect = httpx.ConnectError("unavailable")
    api, calls = client
    for _ in range(2):
        assert api.delete("/admin", headers={
            "Authorization": f"Bearer {token(signing_key, ['Admin'])}",
        }).status_code == 503
    assert fetch.call_count == 1
    calls.clear.assert_not_called()


def test_development_key_is_explicit_and_never_enabled_in_production(client, security):
    settings, _ = security
    api, _ = client
    settings.admin_api_key = "local-test-only"
    assert api.delete("/admin", headers={"X-Admin-Api-Key": "local-test-only"}).status_code == 200
    settings.app_env = "production"
    assert api.delete("/admin", headers={"X-Admin-Api-Key": "local-test-only"}).status_code == 401


def test_invalid_key_does_not_fall_through_to_valid_token(client, security, signing_key):
    settings, _ = security
    settings.admin_api_key = "local-test-only"
    api, calls = client
    assert api.delete("/admin", headers={
        "X-Admin-Api-Key": "wrong",
        "Authorization": f"Bearer {token(signing_key, ['Admin'])}",
    }).status_code == 401
    calls.clear.assert_not_called()


def test_no_role_is_not_reader():
    assert User(user_id=USER).best_role is None
    assert User(user_id=USER, roles=["Unknown"]).best_role is None
    with pytest.raises(ValueError):
        auth.require_role("typo")


@pytest.mark.parametrize("env", ["prod", "production", ""])
def test_development_key_configuration_rejected_outside_development(env):
    settings = Settings(_env_file=None, app_env=env, admin_api_key="test-key")
    assert any("admin_api_key" in error for error in settings.validate_authentication_requirements())


def test_production_auth_cannot_be_disabled_by_relaxed_startup(monkeypatch):
    settings = Settings(
        _env_file=None, app_env="production", startup_strict_in_prod=False,
        azure_ad_tenant_id="", azure_ad_client_id="",
    )
    monkeypatch.setattr(config, "Settings", lambda: settings)
    config.get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="Authentication configuration invalid"):
            config.get_settings()
    finally:
        config.get_settings.cache_clear()


@pytest.mark.parametrize(("tenant", "audience"), [
    ("common", CLIENT), (TENANT, ""), ("", CLIENT), (TENANT, "api://not-a-guid"),
])
def test_invalid_authentication_configuration(tenant, audience):
    settings = Settings(_env_file=None, azure_ad_tenant_id=tenant, azure_ad_client_id=audience)
    assert settings.validate_authentication_requirements()


def test_expired_key_cache_cannot_be_used_during_refresh_backoff(security):
    _, fetch = security
    keys = auth_utils.get_signing_keys(TENANT)
    keys.get("test-key")
    keys._expires_at = 0
    with pytest.raises(HTTPException) as exc:
        keys.get("test-key")
    assert exc.value.status_code == 503
    assert fetch.call_count == 1
