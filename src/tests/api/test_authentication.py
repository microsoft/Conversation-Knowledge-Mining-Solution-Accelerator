import base64
import json
import re
import sqlite3
import time
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jwt.exceptions import PyJWKClientConnectionError

from src.api import config
from src.api.auth import auth_utils
from src.api.modules.security import auth

TENANT_ID = "11111111-1111-4111-8111-111111111111"
CLIENT_ID = "22222222-2222-4222-8222-222222222222"
USER_ID = "33333333-3333-4333-8333-333333333333"
SCRIPT_KEY = "test-only-script-credential"
FORGED_HEADERS = {
    "x-ms-client-principal-id": "attacker",
    "x-ms-client-principal": base64.b64encode(
        json.dumps({"claims": [{"typ": "roles", "val": "Admin"}]}).encode()
    ).decode(),
}


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def make_token(signing_key):
    def create(*, omit=(), key=None, algorithm="RS256", **overrides):
        now = int(time.time())
        claims = {
            "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            "aud": CLIENT_ID,
            "tid": TENANT_ID,
            "oid": USER_ID,
            "sub": "subject",
            "iat": now,
            "nbf": now - 1,
            "exp": now + 300,
            "scp": "access_as_user",
            "name": "Test User",
        }
        claims.update(overrides)
        for claim in omit:
            claims.pop(claim, None)
        return jwt.encode(
            claims, key if key is not None else signing_key,
            algorithm=algorithm, headers={"kid": "test-key"},
        )

    return create


@pytest.fixture
def client(monkeypatch, signing_key):
    settings = config.Settings(
        _env_file=None,
        app_env="local",
        azure_ad_tenant_id=TENANT_ID,
        azure_ad_client_id=CLIENT_ID,
        admin_api_key=SCRIPT_KEY,
    )
    for module in (config, auth_utils, auth):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    public_key = jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key(), as_dict=True)
    public_key["kid"] = "test-key"
    jwks = jwt.PyJWKClient("https://unused.invalid/keys")
    monkeypatch.setattr(jwks, "fetch_data", lambda: {"keys": [public_key]})
    monkeypatch.setattr(auth_utils, "_get_jwks_client", lambda tenant: jwks)

    from src.api import main
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "_RATE_LIMIT", 10000)
    main._rate_buckets.clear()
    with TestClient(main.app, raise_server_exceptions=True) as test_client:
        yield test_client, settings, jwks


@pytest.mark.parametrize("headers", [{}, FORGED_HEADERS])
def test_every_application_route_rejects_anonymous_and_forged_identity(client, headers):
    http, _, _ = client
    for route in http.app.routes:
        if not isinstance(route, APIRoute) or route.path in ("/", "/api/health"):
            continue
        path = re.sub(r"\{[^}]+\}", "example", route.path)
        for method in route.methods:
            response = http.request(method, path, headers=headers)
            assert response.status_code == 401, (method, path, response.text)
            assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("roles", [[], ["Unknown"], ["Reader"]])
def test_roleless_and_reader_users_cannot_mutate_data(client, make_token, roles):
    http, _, _ = client
    headers = {"Authorization": f"Bearer {make_token(roles=roles)}"}
    assert http.get("/api/auth/me", headers=headers).status_code == 200
    for method, path in (
        ("POST", "/api/ingestion/load-default"),
        ("POST", "/api/ingestion/upload/json"),
        ("DELETE", "/api/ingestion/files/example"),
        ("POST", "/api/ingestion/refresh"),
        ("DELETE", "/api/ingestion/clear"),
        ("POST", "/api/pipelines/run"),
        ("POST", "/api/pipelines/upload"),
        ("POST", "/api/processing/batch"),
        ("POST", "/api/documents/extract"),
        ("POST", "/api/embeddings/index"),
        ("DELETE", "/api/embeddings/clear"),
        ("POST", "/api/data-sources/scenario"),
        ("POST", "/api/data-sources/"),
        ("PUT", "/api/data-sources/example"),
        ("DELETE", "/api/data-sources/example"),
        ("POST", "/api/data-sources/test"),
        ("POST", "/api/data-sources/example/ingest"),
        ("POST", "/api/data-sources/quick-connect"),
    ):
        response = http.request(method, path, headers=headers)
        assert response.status_code == 403, (method, path, response.text)


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://attacker.invalid/v2.0"},
        {"aud": "another-api"},
        {"tid": "another-tenant"},
        {"exp": 1},
        {"nbf": 4102444800},
        {"iat": 4102444800},
        {"oid": ""},
        {"roles": "Admin"},
        {"roles": [None]},
        {"scp": "User.Read", "roles": ["Admin"]},
        {"scp": None},
        {"name": []},
    ],
)
def test_invalid_token_claims_are_rejected(client, make_token, overrides):
    http, _, _ = client
    response = http.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {make_token(**overrides)}"}
    )
    assert response.status_code == 401


@pytest.mark.parametrize("claim", ["exp", "iss", "aud", "tid", "oid", "sub", "nbf", "iat"])
def test_missing_required_claims_are_rejected(client, make_token, claim):
    http, _, _ = client
    response = http.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {make_token(omit=(claim,))}"}
    )
    assert response.status_code == 401


def test_bad_signature_and_disallowed_algorithms_are_rejected(client, make_token):
    http, _, _ = client
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    valid_token = make_token()
    unsigned = jwt.encode(
        jwt.decode(valid_token, options={"verify_signature": False}),
        key=None, algorithm="none", headers={"kid": "test-key"},
    )
    for token in (
        make_token(key=other_key),
        make_token(key="test-only-hmac-key-with-at-least-32-bytes", algorithm="HS256"),
        unsigned,
        "not-a-token",
    ):
        response = http.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


def test_id_tokens_are_not_accepted_as_access_tokens(client, make_token):
    http, _, _ = client
    response = http.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {make_token(omit=('scp',), roles=['Admin'])}"},
    )
    assert response.status_code == 401


def test_application_token_requires_app_identity_and_assigned_role(client, make_token):
    http, _, _ = client
    token = make_token(omit=("scp",), idtyp="app", roles=["Contributor"])
    assert http.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    ).status_code == 200


@pytest.mark.parametrize(
    ("roles", "contributor_status", "admin_status"),
    [([], 403, 403), (["Contributor"], 200, 403), (["Admin"], 200, 200)],
)
def test_validated_roles_control_real_operations(
    client, make_token, monkeypatch, roles, contributor_status, admin_status
):
    from src.api.modules.ingestion import router as ingestion
    from src.api.modules.embeddings import router as embeddings

    http, _, _ = client
    load = Mock(return_value={"total_loaded": 0, "by_type": {}, "sample_ids": []})
    clear = Mock()
    monkeypatch.setattr(ingestion.ingestion_service, "load_default_dataset", load)
    monkeypatch.setattr(ingestion, "_trigger_auto_pipeline", lambda: None)
    monkeypatch.setattr(embeddings.embeddings_service, "clear", clear)
    headers = {"Authorization": f"Bearer {make_token(roles=roles)}", **FORGED_HEADERS}
    assert http.post("/api/ingestion/load-default", headers=headers).status_code == contributor_status
    assert http.delete("/api/embeddings/clear", headers=headers).status_code == admin_status
    assert load.call_count == (1 if contributor_status == 200 else 0)
    assert clear.call_count == (1 if admin_status == 200 else 0)


def test_chat_identity_comes_from_validated_token_not_client_headers(client, make_token, monkeypatch):
    from src.api.storage.db_service import db_service

    http, _, _ = client
    list_sessions = Mock(return_value=[])
    monkeypatch.setattr(db_service, "list_sessions", list_sessions)
    response = http.get(
        "/api/rag/chat/sessions?user_id=attacker",
        headers={"Authorization": f"Bearer {make_token()}", **FORGED_HEADERS},
    )
    assert response.status_code == 200
    list_sessions.assert_called_once_with(USER_ID)


@pytest.fixture
def chat_database(monkeypatch):
    from src.api.storage.chat_store import ChatStore
    from src.api.storage.db_service import db_service

    database = sqlite3.connect(":memory:", check_same_thread=False)
    database.executescript("""
        CREATE TABLE chat_sessions (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT, message_count INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE chat_messages (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, role TEXT, content TEXT,
            sources TEXT, sort_order INTEGER, timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    class Cursor:
        def __init__(self):
            self.cursor = database.cursor()

        def execute(self, query, *parameters):
            query = query.replace(" WITH (UPDLOCK, HOLDLOCK)", "")
            query = query.replace("GETUTCDATE()", "CURRENT_TIMESTAMP")
            self.cursor.execute(query, parameters)
            return self

        def fetchone(self):
            return self.cursor.fetchone()

        @property
        def rowcount(self):
            return self.cursor.rowcount

    connection = Mock()
    connection.cursor.side_effect = Cursor
    connection.commit.side_effect = database.commit
    connection.rollback.side_effect = database.rollback
    sql = Mock(available=True)
    sql._get_connection.return_value = connection
    store = ChatStore()
    monkeypatch.setattr(store, "_get_sql", lambda: sql)
    monkeypatch.setattr(db_service, "_provider", "sql")
    monkeypatch.setattr(db_service, "_chat", store)
    monkeypatch.setattr(db_service, "_data", sql)
    yield database, store, connection
    database.close()


def test_chat_save_rejects_another_users_session(client, make_token, monkeypatch, chat_database):
    from src.api.modules.rag import router as rag

    http, _, _ = client
    database, store, _ = chat_database
    store.create_session("victim", title="Victim title", session_id="victim-session")
    store.save_messages_bulk(
        "victim-session", "victim", [{"role": "user", "content": "Victim message"}],
    )
    monkeypatch.setattr(rag.rag_service, "generate_title", Mock(return_value="Forged title"))
    response = http.post(
        "/api/rag/chat/save",
        headers={"Authorization": f"Bearer {make_token()}"},
        json={
            "session_id": "victim-session", "user_id": "victim",
            "messages": [{"role": "user", "content": "Forged message"}],
        },
    )
    assert response.status_code == 409
    assert database.execute("SELECT title, user_id FROM chat_sessions").fetchall() == [
        ("Victim title", "victim")
    ]
    assert database.execute("SELECT content FROM chat_messages").fetchall() == [("Victim message",)]


def test_chat_save_creates_and_updates_owned_sessions(client, make_token, monkeypatch, chat_database):
    from src.api.modules.rag import router as rag

    http, _, _ = client
    database, _, _ = chat_database
    title = Mock(return_value="Generated title")
    monkeypatch.setattr(rag.rag_service, "generate_title", title)
    headers = {"Authorization": f"Bearer {make_token()}"}
    for content in ("First message", "Replacement message"):
        response = http.post(
            "/api/rag/chat/save", headers=headers,
            json={
                "session_id": "owned-session", "user_id": "forged-user",
                "messages": [{"role": "user", "content": content}],
            },
        )
        assert response.status_code == 200
        assert response.json() == {"saved": True}
    title.assert_called_once()
    assert database.execute("SELECT user_id, title, message_count FROM chat_sessions").fetchall() == [
        (USER_ID, "Generated title", 1)
    ]
    assert database.execute("SELECT content FROM chat_messages").fetchall() == [("Replacement message",)]


def test_chat_store_enforces_ownership_for_messages_and_metadata(chat_database):
    database, store, _ = chat_database
    store.create_session("victim", title="Victim title", session_id="victim-session")
    store.save_messages_bulk("victim-session", "victim", [{"content": "Victim message"}])
    assert not store.save_messages_bulk(
        "victim-session", USER_ID, [{"content": "Forged message"}], title="Forged title",
    )
    assert not store.update_session("victim-session", USER_ID, title="Forged title")
    assert database.execute("SELECT title, message_count FROM chat_sessions").fetchall() == [
        ("Victim title", 1)
    ]
    assert database.execute("SELECT content FROM chat_messages").fetchall() == [("Victim message",)]


def test_chat_save_rolls_back_messages_and_metadata_on_database_failure(
    client, make_token, chat_database
):
    http, _, _ = client
    database, store, connection = chat_database
    store.create_session(USER_ID, title="Original title", session_id="owned-session")
    store.save_messages_bulk("owned-session", USER_ID, [{"content": "Original message"}])
    original_cursor = connection.cursor.side_effect

    def failing_cursor():
        cursor = original_cursor()
        execute = cursor.execute

        def fail_update(query, *parameters):
            if query.startswith("UPDATE chat_sessions"):
                raise RuntimeError("Simulated SQL write failure")
            return execute(query, *parameters)

        cursor.execute = fail_update
        return cursor

    connection.cursor.side_effect = failing_cursor
    response = http.post(
        "/api/rag/chat/save",
        headers={"Authorization": f"Bearer {make_token()}"},
        json={"session_id": "owned-session", "messages": [{"content": "Replacement message"}]},
    )
    assert response.status_code == 500
    assert database.execute("SELECT title, message_count FROM chat_sessions").fetchall() == [
        ("Original title", 1)
    ]
    assert database.execute("SELECT content FROM chat_messages").fetchall() == [("Original message",)]


def test_cosmos_save_rejects_missing_foreign_or_ambiguous_session_ownership():
    from src.api.storage.cosmos_service import CosmosService

    store = CosmosService()
    store._initialized = True
    store._db = Mock()
    sessions = Mock()
    messages = Mock()
    store._db.get_container_client.side_effect = lambda name: (
        sessions if name == store.SESSIONS_CONTAINER else messages
    )
    for owners in ([], [{"user_id": "victim"}], [{"user_id": USER_ID}, {"user_id": "victim"}]):
        sessions.query_items.return_value = owners
        assert not store.save_messages_bulk("victim-session", USER_ID, [{"content": "Forged"}])
    messages.query_items.assert_not_called()
    messages.create_item.assert_not_called()
    sessions.replace_item.assert_not_called()


def test_cosmos_save_preserves_owned_session_behavior():
    from src.api.storage.cosmos_service import CosmosService

    store = CosmosService()
    store._initialized = True
    store._db = Mock()
    sessions = Mock()
    messages = Mock()
    store._db.get_container_client.side_effect = lambda name: (
        sessions if name == store.SESSIONS_CONTAINER else messages
    )
    sessions.query_items.return_value = [{"user_id": USER_ID}]
    sessions.read_item.return_value = {"id": "owned-session", "user_id": USER_ID, "title": "Original"}
    messages.query_items.return_value = [{"id": "old-message"}]
    assert store.save_messages_bulk("owned-session", USER_ID, [{"content": "Replacement"}])
    messages.delete_item.assert_called_once_with(item="old-message", partition_key="owned-session")
    assert messages.create_item.call_args.args[0]["content"] == "Replacement"
    metadata = sessions.replace_item.call_args.kwargs["body"]
    assert metadata["user_id"] == USER_ID
    assert metadata["title"] == "Original"
    assert metadata["message_count"] == 1


def test_script_key_remains_supported_but_is_never_an_anonymous_fallback(client, monkeypatch):
    from src.api.modules.embeddings import router as embeddings

    http, settings, _ = client
    clear = Mock()
    monkeypatch.setattr(embeddings.embeddings_service, "clear", clear)
    assert http.delete(
        "/api/embeddings/clear", headers={"X-Admin-Api-Key": SCRIPT_KEY}
    ).status_code == 200
    clear.assert_called_once()
    assert http.get("/api/auth/me", headers={"X-Admin-Api-Key": "wrong"}).status_code == 401
    settings.admin_api_key = ""
    assert http.get(
        "/api/auth/me", headers={"X-Admin-Api-Key": SCRIPT_KEY}
    ).status_code == 401


def test_missing_auth_configuration_and_unavailable_keys_fail_closed(client, make_token, monkeypatch):
    http, settings, jwks = client
    headers = {"Authorization": f"Bearer {make_token()}"}
    settings.azure_ad_client_id = ""
    assert http.get("/api/auth/me", headers=headers).status_code == 503
    assert http.get("/api/auth/me", headers=FORGED_HEADERS).status_code == 401
    settings.azure_ad_client_id = CLIENT_ID
    monkeypatch.setattr(jwks, "fetch_data", Mock(side_effect=PyJWKClientConnectionError("offline")))
    assert http.get("/api/auth/me", headers=headers).status_code == 503


def test_health_checks_and_cors_preflight_do_not_require_credentials(client):
    http, _, _ = client
    assert http.get("/").status_code == 200
    response = http.get("/api/health")
    assert response.status_code in (200, 503)
    assert "checks" in response.json()
    response = http.options(
        "/api/ingestion/documents",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200


def test_unknown_required_roles_are_configuration_errors():
    with pytest.raises(ValueError, match="Unknown required role"):
        auth.require_role("contributer")
