import pytest
from unittest.mock import patch, MagicMock
from agents.chart_agent_factory import ChartAgentFactory


@pytest.mark.asyncio
@patch("agents.chart_agent_factory.AIProjectClient")
@patch("agents.chart_agent_factory.get_azure_credential")
async def test_create_agent_success(mock_get_azure_credential, mock_ai_project_client_class):
    # Mock config
    mock_config = MagicMock()
    mock_config.ai_project_endpoint = "https://example-endpoint/"
    mock_config.ai_project_api_version = "2024-04-01-preview"
    mock_config.azure_openai_deployment_model = "gpt-4"
    mock_config.solution_name = "TestSolution"

    # Mock client and agent
    mock_agent = MagicMock()
    mock_client = MagicMock()
    mock_client.agents.create_agent.return_value = mock_agent
    mock_ai_project_client_class.return_value = mock_client
    mock_get_azure_credential.return_value = MagicMock()

    # Call create_agent
    result = await ChartAgentFactory.create_agent(mock_config)

    # Assertions
    assert result["agent"] == mock_agent
    assert result["client"] == mock_client
    mock_ai_project_client_class.assert_called_once_with(
        endpoint=mock_config.ai_project_endpoint,
        credential=mock_get_azure_credential.return_value,
        api_version=mock_config.ai_project_api_version
    )
    mock_client.agents.create_agent.assert_called_once()


@pytest.mark.asyncio
async def test_delete_agent_instance():
    mock_client = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "mock-agent-id"
    
    agent_wrapper = {
        "agent": mock_agent,
        "client": mock_client
    }

    await ChartAgentFactory._delete_agent_instance(agent_wrapper)

    mock_client.agents.delete_agent.assert_called_once_with("mock-agent-id")
