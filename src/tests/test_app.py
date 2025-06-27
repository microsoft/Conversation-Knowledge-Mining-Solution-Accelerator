import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

import app as app_module


@pytest.fixture
def mock_agent():
    return AsyncMock()


@pytest_asyncio.fixture
async def test_app(mock_agent):
    with patch("app.AgentFactory.get_instance", return_value=mock_agent), \
         patch("app.AgentFactory.delete_instance", new_callable=AsyncMock):
        app = app_module.build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield app, ac


@pytest.mark.asyncio
async def test_health_check(test_app):
    app, client = test_app
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_lifespan_startup_and_shutdown(mock_agent):
    with patch("app.AgentFactory.get_instance", return_value=mock_agent) as mock_get_instance, \
         patch("app.AgentFactory.delete_instance", new_callable=AsyncMock) as mock_delete_instance:

        app = app_module.build_app()

        # Manually trigger lifespan events
        async with app_module.lifespan(app):
            mock_get_instance.assert_called_once()
            assert hasattr(app.state, "agent")
            assert app.state.agent == mock_agent

        mock_delete_instance.assert_awaited_once()
        assert app.state.agent is None


def test_build_app_sets_metadata():
    app = app_module.build_app()
    assert isinstance(app, FastAPI)
    assert app.title == "Conversation Knowledge Mining Solution Accelerator"
    assert app.version == "1.0.0"


def test_routes_registered():
    app = app_module.build_app()
    route_paths = [route.path for route in app.routes]

    assert "/health" in route_paths
    assert any(route.path.startswith("/api") for route in app.routes)
    assert any(route.path.startswith("/history") for route in app.routes)
