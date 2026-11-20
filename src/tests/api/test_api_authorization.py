import importlib
import re
from unittest.mock import Mock

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.api import config
from src.api.modules.security import auth
from src.api.modules.security.models import User


@pytest.fixture
def application(monkeypatch):
    settings = config.Settings(
        _env_file=None,
        app_env="local",
        azure_ad_tenant_id="",
        azure_ad_client_id="",
        admin_api_key="",
        azure_ai_agent_endpoint="",
        azure_foundry_endpoint="",
        azure_openai_endpoint="",
        azure_search_endpoint="",
        azure_content_understanding_endpoint="",
        azure_storage_account="",
        azure_sql_server="",
        azure_cosmos_endpoint="",
    )
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    main = importlib.import_module("src.api.main")
    main._rate_buckets.clear()
    yield main.app
    main.app.dependency_overrides.clear()
    main._rate_buckets.clear()


def test_every_business_endpoint_rejects_anonymous_requests(application):
    api = TestClient(application)
    tested = 0
    for route in application.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        if route.path == "/api/health":
            continue
        assert route.dependant.dependencies, f"Missing API protection: {route.path}"
        path = re.sub(r"\{[^}]+\}", "test-id", route.path)
        for method in route.methods:
            response = api.request(method, path, json={})
            assert response.status_code == 401, (method, path, response.text)
            assert response.headers["www-authenticate"] == "Bearer"
            # The rate limiter must not obscure the remaining authorization checks.
            import src.api.main as main
            main._rate_buckets.clear()
            tested += 1
    assert tested >= 60


def test_only_minimal_health_is_public(application):
    api = TestClient(application)
    assert api.get("/").json()["status"] == "healthy"
    assert api.get("/api/health").json() == {"status": "healthy"}
    assert api.get("/api/health/details").status_code == 401


@pytest.mark.parametrize("role", [None, "Unknown", "Reader", "Contributor"])
def test_non_admin_cannot_clear_persistent_ingestion(application, monkeypatch, role):
    from src.api.modules.ingestion.service import ingestion_service

    clear = Mock()
    monkeypatch.setattr(ingestion_service, "clear", clear)
    application.dependency_overrides[auth.get_current_user] = lambda: User(
        user_id="test-user", roles=[] if role is None else [role],
    )
    assert TestClient(application).delete("/api/ingestion/clear").status_code == 403
    clear.assert_not_called()


@pytest.mark.parametrize(("method", "path", "body"), [
    ("POST", "/api/ingestion/refresh", {}),
    ("POST", "/api/ingestion/upload/json", {}),
    ("DELETE", "/api/ingestion/files/test-id", {}),
    ("POST", "/api/pipelines/run", {}),
    ("POST", "/api/pipelines/upload", {}),
    ("POST", "/api/processing/batch", {}),
    ("POST", "/api/processing/summarize", {}),
    ("POST", "/api/processing/extract-entities", {}),
    ("POST", "/api/documents/extract", {}),
    ("POST", "/api/embeddings/generate", {}),
    ("POST", "/api/embeddings/index", {}),
    ("DELETE", "/api/embeddings/clear", {}),
    ("POST", "/api/data-sources/", {}),
    ("POST", "/api/data-sources/quick-connect", {}),
    ("DELETE", "/api/data-sources/test-id", {}),
    ("POST", "/api/pipelines/reload", {}),
])
def test_reader_cannot_invoke_mutations(application, method, path, body):
    application.dependency_overrides[auth.get_current_user] = lambda: User(
        user_id="reader", roles=["Reader"],
    )
    assert TestClient(application).request(method, path, json=body).status_code == 403


def test_admin_can_clear_fixture_data(application, monkeypatch):
    from src.api.modules.ingestion.service import ingestion_service
    from src.api.modules.insights.service import dashboard_service

    clear = Mock()
    monkeypatch.setattr(ingestion_service, "clear", clear)
    monkeypatch.setattr(dashboard_service, "_plan_cache", {})
    monkeypatch.setattr(dashboard_service, "_plan_cache_ts", {})
    monkeypatch.setattr(dashboard_service, "_schema_cache", None)
    monkeypatch.setattr(dashboard_service, "_schema_hash", None)
    application.dependency_overrides[auth.get_current_user] = lambda: User(
        user_id="admin", roles=["Admin"],
    )
    response = TestClient(application).delete("/api/ingestion/clear")
    assert response.status_code == 200
    clear.assert_called_once_with()


def test_reader_can_read_documents(application, monkeypatch):
    from src.api.modules.ingestion.service import ingestion_service

    read = Mock(return_value=[])
    monkeypatch.setattr(ingestion_service, "search_documents", read)
    application.dependency_overrides[auth.get_current_user] = lambda: User(
        user_id="reader", roles=["Reader"],
    )
    assert TestClient(application).get("/api/ingestion/documents").json() == []
    read.assert_called_once()


def test_cors_preflight_allows_bearer_authentication(application):
    response = TestClient(application).options("/api/ingestion/documents", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_rag_uses_verified_identity_not_headers(application, monkeypatch):
    from src.api.storage.db_service import db_service

    sessions = Mock(return_value=[])
    monkeypatch.setattr(db_service, "list_sessions", sessions)
    application.dependency_overrides[auth.get_current_user] = lambda: User(
        user_id="verified-user", roles=["Reader"],
    )
    response = TestClient(application).get("/api/rag/chat/sessions", headers={
        "X-Ms-Client-Principal-Id": "spoofed-user",
    })
    assert response.status_code == 200
    sessions.assert_called_once_with("verified-user")


@pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
def test_foreign_chat_session_does_not_disclose_or_modify_history(application, monkeypatch, method):
    from src.api.storage.db_service import DbService, db_service

    monkeypatch.setattr(DbService, "available", property(lambda self: True))
    monkeypatch.setattr(db_service, "get_session", Mock(return_value=None))
    create = Mock(return_value=None)
    save = Mock()
    load = Mock()
    delete = Mock(return_value=False)
    monkeypatch.setattr(db_service, "create_session", create)
    monkeypatch.setattr(db_service, "save_messages_bulk", save)
    monkeypatch.setattr(db_service, "get_messages", load)
    monkeypatch.setattr(db_service, "delete_session", delete)
    application.dependency_overrides[auth.get_current_user] = lambda: User(
        user_id="attacker", roles=["Reader"],
    )
    api = TestClient(application)
    if method == "POST":
        response = api.post("/api/rag/chat/save", json={
            "session_id": "victim", "messages": [], "user_id": "victim-owner",
        })
        assert response.status_code == 409
        create.assert_called_once_with(session_id="victim", user_id="attacker", title="Chat session")
    elif method == "GET":
        assert api.get("/api/rag/chat/load/victim").status_code == 404
    else:
        assert api.delete("/api/rag/chat/session/victim").status_code == 404
        delete.assert_called_once_with("victim", "attacker")
    save.assert_not_called()
    load.assert_not_called()


def test_existing_chat_save_uses_owner_lookup_not_capped_session_list(application, monkeypatch):
    from src.api.storage.db_service import DbService, db_service

    monkeypatch.setattr(DbService, "available", property(lambda self: True))
    monkeypatch.setattr(db_service, "get_session", Mock(return_value={"id": "owned"}))
    listing = Mock()
    create = Mock()
    save = Mock(return_value=True)
    monkeypatch.setattr(db_service, "list_sessions", listing)
    monkeypatch.setattr(db_service, "create_session", create)
    monkeypatch.setattr(db_service, "save_messages_bulk", save)
    application.dependency_overrides[auth.get_current_user] = lambda: User(
        user_id="owner", roles=["Reader"],
    )
    response = TestClient(application).post("/api/rag/chat/save", json={
        "session_id": "owned", "messages": [{"content": "Updated"}], "user_id": "forged",
    })
    assert response.json() == {"saved": True}
    save.assert_called_once_with("owned", [{"content": "Updated"}], "owner", title=None)
    listing.assert_not_called()
    create.assert_not_called()
