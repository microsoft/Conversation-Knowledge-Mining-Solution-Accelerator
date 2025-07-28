import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

import app as app_module


@pytest_asyncio.fixture
async def test_app():
    with patch("agents.conversation_agent_factory.ConversationAgentFactory.get_agent", new_callable=AsyncMock) as mock_convo_agent, \
         patch("agents.search_agent_factory.SearchAgentFactory.get_agent", new_callable=AsyncMock) as mock_search_agent, \
         patch("agents.sql_agent_factory.SQLAgentFactory.get_agent", new_callable=AsyncMock) as mock_sql_agent, \
         patch("agents.conversation_agent_factory.ConversationAgentFactory.delete_agent", new_callable=AsyncMock) as mock_delete_convo, \
         patch("agents.search_agent_factory.SearchAgentFactory.delete_agent", new_callable=AsyncMock) as mock_delete_search, \
         patch("agents.sql_agent_factory.SQLAgentFactory.delete_agent", new_callable=AsyncMock) as mock_delete_sql:

        mock_convo_agent.return_value = AsyncMock(name="ConversationAgent")
        mock_search_agent.return_value = AsyncMock(name="SearchAgent")
        mock_sql_agent.return_value = AsyncMock(name="SQLAgent")

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
async def test_lifespan_startup_and_shutdown():
    mock_convo_agent = AsyncMock(name="ConversationAgent")
    mock_search_agent = AsyncMock(name="SearchAgent")
    mock_sql_agent = AsyncMock(name="SQLAgent")
    mock_chart_agent = AsyncMock(name="ChartAgent")

    with patch("agents.conversation_agent_factory.ConversationAgentFactory.get_agent", return_value=mock_convo_agent) as mock_get_convo, \
         patch("agents.search_agent_factory.SearchAgentFactory.get_agent", return_value=mock_search_agent) as mock_get_search, \
         patch("agents.sql_agent_factory.SQLAgentFactory.get_agent", return_value=mock_sql_agent) as mock_get_sql, \
         patch("agents.chart_agent_factory.ChartAgentFactory.get_agent", return_value=mock_chart_agent) as mock_get_chart, \
         patch("agents.conversation_agent_factory.ConversationAgentFactory.delete_agent", new_callable=AsyncMock) as mock_delete_convo, \
         patch("agents.search_agent_factory.SearchAgentFactory.delete_agent", new_callable=AsyncMock) as mock_delete_search, \
         patch("agents.sql_agent_factory.SQLAgentFactory.delete_agent", new_callable=AsyncMock) as mock_delete_sql, \
         patch("agents.chart_agent_factory.ChartAgentFactory.delete_agent", new_callable=AsyncMock) as mock_delete_chart:

        app = app_module.build_app()

        async with app_module.lifespan(app):
            mock_get_convo.assert_awaited_once()
            mock_get_search.assert_awaited_once()
            mock_get_sql.assert_awaited_once()
            mock_get_chart.assert_awaited_once()

            assert app.state.agent == mock_convo_agent
            assert app.state.search_agent == mock_search_agent
            assert app.state.sql_agent == mock_sql_agent
            assert app.state.chart_agent == mock_chart_agent

        mock_delete_convo.assert_awaited_once()
        mock_delete_search.assert_awaited_once()
        mock_delete_sql.assert_awaited_once()
        mock_delete_chart.assert_awaited_once()

        assert app.state.agent is None
        assert app.state.search_agent is None
        assert app.state.sql_agent is None
        assert app.state.chart_agent is None


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
