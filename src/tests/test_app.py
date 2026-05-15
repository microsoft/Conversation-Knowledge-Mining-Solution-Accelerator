import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

import app as app_module


@pytest_asyncio.fixture
async def test_app():
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


# Removed test_lifespan_startup_and_shutdown as agent factories no longer exist in v2


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
