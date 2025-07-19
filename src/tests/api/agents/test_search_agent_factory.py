import pytest
from unittest.mock import patch, MagicMock
from agents.search_agent_factory import SearchAgentFactory


@pytest.fixture(autouse=True)
def reset_search_agent_factory():
    SearchAgentFactory._agent = None
    yield
    SearchAgentFactory._agent = None


@pytest.mark.asyncio
@patch("agents.search_agent_factory.DefaultAzureCredential", autospec=True)
@patch("agents.search_agent_factory.AIProjectClient", autospec=True)
@patch("agents.search_agent_factory.AzureAISearchTool", autospec=True)
async def test_create_agent_creates_new_instance(
    mock_search_tool_cls,
    mock_project_client_cls,
    mock_credential_cls
):
    # Mock config
    mock_config = MagicMock()
    mock_config.ai_project_endpoint = "https://fake-endpoint"
    mock_config.azure_ai_search_connection_name = "fake-connection"
    mock_config.azure_ai_search_index = "fake-index"
    mock_config.azure_openai_deployment_model = "fake-model"
    mock_config.solution_name = "test-solution"
    mock_config.ai_project_api_version = "2025-05-01"

    # Mock project client
    mock_project_client = MagicMock()
    mock_project_client_cls.return_value = mock_project_client

    # Mock index response
    mock_index = MagicMock()
    mock_index.name = "index-name"
    mock_index.version = "1"
    mock_project_client.indexes.create_or_update.return_value = mock_index

    # Mock search tool
    mock_search_tool_instance = MagicMock()
    mock_search_tool_instance.definitions = ["tool-def"]
    mock_search_tool_instance.resources = ["tool-res"]
    mock_search_tool_cls.return_value = mock_search_tool_instance

    # Mock agent
    mock_agent = MagicMock()
    mock_project_client.agents.create_agent.return_value = mock_agent

    # Run the factory directly
    result = await SearchAgentFactory.create_agent(mock_config)

    assert result["agent"] == mock_agent
    assert result["client"] == mock_project_client

    mock_project_client.indexes.create_or_update.assert_called_once_with(
        name="project-index-fake-connection-fake-index",
        version="1",
        index={
            "connectionName": "fake-connection",
            "indexName": "fake-index",
            "type": "AzureSearch",
            "fieldMapping": {
                "contentFields": ["content"],
                "urlField": "sourceurl",
                "titleField": "chunk_id",
            }
        }
    )
    mock_project_client.agents.create_agent.assert_called_once()


@pytest.mark.asyncio
async def test_get_agent_returns_existing_instance():
    # Setup: Already initialized
    SearchAgentFactory._agent = {"agent": MagicMock(), "client": MagicMock()}
    result = await SearchAgentFactory.get_agent()
    assert result == SearchAgentFactory._agent


@pytest.mark.asyncio
async def test_delete_agent_removes_agent():
    # Setup
    mock_agent = MagicMock()
    mock_agent.id = "mock-agent-id"
    mock_client = MagicMock()

    SearchAgentFactory._agent = {"agent": mock_agent, "client": mock_client}

    await SearchAgentFactory.delete_agent()

    mock_client.agents.delete_agent.assert_called_once_with("mock-agent-id")
    assert SearchAgentFactory._agent is None


@pytest.mark.asyncio
async def test_delete_agent_does_nothing_if_none():
    SearchAgentFactory._agent = None
    await SearchAgentFactory.delete_agent()
    # No error should be raised, and nothing is called

