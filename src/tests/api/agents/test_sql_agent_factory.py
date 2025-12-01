import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from agents.sql_agent_factory import SQLAgentFactory


@pytest.fixture(autouse=True)
def reset_sql_agent_factory():
    SQLAgentFactory._agent = None
    yield
    SQLAgentFactory._agent = None


@pytest.mark.asyncio
@patch("agents.sql_agent_factory.AIProjectClient", autospec=True)
@patch("agents.sql_agent_factory.get_azure_credential")
async def test_create_agent_creates_new_instance(
    mock_get_azure_credential,
    mock_ai_client_cls
):
    # Mock config
    mock_config = MagicMock()
    mock_config.ai_project_endpoint = "https://test-endpoint"
    mock_config.ai_project_api_version = "2025-05-01"
    mock_config.azure_openai_deployment_model = "test-model"
    mock_config.solution_name = "test-solution"

    # Mock credential
    mock_get_azure_credential.return_value = MagicMock()

    # Mock project client
    mock_project_client = MagicMock()
    mock_ai_client_cls.return_value = mock_project_client

    # Mock agent
    mock_agent = MagicMock()
    mock_project_client.agents.create_agent.return_value = mock_agent

    result = await SQLAgentFactory.create_agent(mock_config)

    assert result["agent"] == mock_agent
    assert result["client"] == mock_project_client

    mock_ai_client_cls.assert_called_once_with(
        endpoint="https://test-endpoint",
        credential=mock_get_azure_credential.return_value,
        api_version="2025-05-01"
    )
    mock_project_client.agents.create_agent.assert_called_once()
    args, kwargs = mock_project_client.agents.create_agent.call_args
    assert kwargs["model"] == "test-model"
    assert kwargs["name"] == "KM-ChatWithSQLDatabaseAgent-test-solution"
    assert "Generate a valid T-SQL query" in kwargs["instructions"]


@pytest.mark.asyncio
async def test_get_agent_returns_existing_instance():
    SQLAgentFactory._agent = {"agent": MagicMock(), "client": MagicMock()}
    result = await SQLAgentFactory.get_agent()
    assert result == SQLAgentFactory._agent


@pytest.mark.asyncio
async def test_delete_agent_removes_agent():
    mock_agent = MagicMock()
    mock_agent.id = "agent-id"

    mock_client = MagicMock()
    mock_client.agents.delete_agent = MagicMock()

    SQLAgentFactory._agent = {
        "agent": mock_agent,
        "client": mock_client
    }

    await SQLAgentFactory.delete_agent()

    mock_client.agents.delete_agent.assert_called_once_with("agent-id")
    assert SQLAgentFactory._agent is None


@pytest.mark.asyncio
async def test_delete_agent_does_nothing_if_none():
    SQLAgentFactory._agent = None
    await SQLAgentFactory.delete_agent()
    # Nothing should raise, nothing should be called