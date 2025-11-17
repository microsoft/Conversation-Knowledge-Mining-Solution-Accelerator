import pytest
from unittest.mock import AsyncMock, patch, MagicMock, ANY

from agents.conversation_agent_factory import ConversationAgentFactory


@pytest.fixture(autouse=True)
def reset_conversation_agent_factory():
    ConversationAgentFactory._agent = None
    yield
    ConversationAgentFactory._agent = None


@pytest.mark.asyncio
@patch("agents.conversation_agent_factory.AIProjectClient", autospec=True)
@patch("agents.conversation_agent_factory.get_azure_credential_async", new_callable=AsyncMock)
@patch("agents.agent_factory_base.Config", autospec=True)
async def test_get_agent_creates_new_instance(
    mock_config_class,
    mock_get_azure_credential_async,
    mock_ai_project_client
):
    # Set up config mock
    mock_config = MagicMock()
    mock_config.ai_project_endpoint = "https://test-endpoint"
    mock_config.azure_openai_deployment_model = "test-model"
    mock_config.solution_name = "test-solution"
    mock_config_class.return_value = mock_config

    # Set up credential mock
    mock_credential = AsyncMock()
    mock_get_azure_credential_async.return_value = mock_credential

    # Set up client mock
    mock_client_instance = AsyncMock()
    mock_agent_definition = MagicMock()
    mock_client_instance.agents.create_agent.return_value = mock_agent_definition
    mock_ai_project_client.return_value = mock_client_instance

    result = await ConversationAgentFactory.get_agent()

    assert result == mock_agent_definition
    mock_ai_project_client.assert_called_once_with(
        credential=mock_credential,
        endpoint="https://test-endpoint"
    )
    mock_client_instance.agents.create_agent.assert_awaited_once_with(
        model="test-model",
        name="KM-ConversationKnowledgeAgent-test-solution",
        instructions=ANY
    )


@pytest.mark.asyncio
async def test_get_agent_returns_existing_instance():
    ConversationAgentFactory._agent = MagicMock()
    result = await ConversationAgentFactory.get_agent()
    assert result == ConversationAgentFactory._agent


@pytest.mark.asyncio
@patch("agents.conversation_agent_factory.AIProjectClient", autospec=True)
@patch("agents.conversation_agent_factory.ChatService", autospec=True)
@patch("agents.agent_factory_base.Config", autospec=True)
async def test_delete_agent_deletes_threads_and_agent(
    mock_config_class,
    mock_chat_service,
    mock_ai_project_client
):
    # Set up config mock
    mock_config = MagicMock()
    mock_config.ai_project_endpoint = "https://test-endpoint"
    mock_config_class.return_value = mock_config

    # Set up agent and client mock
    mock_agent = MagicMock()
    ConversationAgentFactory._agent = mock_agent
    
    # Set up credential mock
    mock_credential = AsyncMock()
    with patch("agents.conversation_agent_factory.get_azure_credential_async", 
              new_callable=AsyncMock, return_value=mock_credential):
        
        # Set up client mock
        mock_client = AsyncMock()
        mock_ai_project_client.return_value = mock_client
        
        # Set up thread cache
        mock_chat_service.thread_cache = {
            "c1": "t1",
            "c2": "t2"
        }

        await ConversationAgentFactory.delete_agent()
        
        # Verify that threads were deleted
        mock_client.agents.threads.delete.assert_any_call("t1")
        mock_client.agents.threads.delete.assert_any_call("t2")
        assert mock_client.agents.threads.delete.await_count == 2
        
        # Verify that agent was deleted
        mock_client.agents.delete_agent.assert_awaited_once_with(mock_agent.id)
        assert ConversationAgentFactory._agent is None


@pytest.mark.asyncio
@patch("agents.conversation_agent_factory.AIProjectClient", autospec=True)
@patch("agents.conversation_agent_factory.ChatService", autospec=True)
@patch("agents.agent_factory_base.Config", autospec=True)
async def test_delete_agent_handles_missing_thread_cache(
    mock_config_class,
    mock_chat_service,
    mock_ai_project_client
):
    # Set up config mock
    mock_config = MagicMock()
    mock_config.ai_project_endpoint = "https://test-endpoint"
    mock_config_class.return_value = mock_config
    
    # Set up agent mock
    mock_agent = MagicMock()
    mock_agent.id = "agent-id"
    ConversationAgentFactory._agent = mock_agent
    
    # Set up credential mock
    mock_credential = AsyncMock()
    with patch("agents.conversation_agent_factory.get_azure_credential_async", 
              new_callable=AsyncMock, return_value=mock_credential):
        
        # Set up client mock
        mock_client = AsyncMock()
        mock_ai_project_client.return_value = mock_client
        
        # Ensure thread_cache doesn't exist
        if hasattr(mock_chat_service, 'thread_cache'):
            delattr(mock_chat_service, 'thread_cache')

        await ConversationAgentFactory.delete_agent()

        # Verify agent deletion (but no thread deletions)
        mock_client.agents.delete_agent.assert_awaited_once_with(mock_agent.id)
        assert ConversationAgentFactory._agent is None


@pytest.mark.asyncio
async def test_delete_agent_does_nothing_if_none():
    ConversationAgentFactory._agent = None
    await ConversationAgentFactory.delete_agent()
    # No assertions needed - test passes if no exception is raised


@pytest.mark.asyncio
@patch("agents.conversation_agent_factory.AIProjectClient", autospec=True)
@patch("agents.conversation_agent_factory.get_azure_credential_async", new_callable=AsyncMock)
async def test_create_agent(
    mock_get_azure_credential_async,
    mock_ai_project_client
):
    # Set up config mock
    mock_config = MagicMock()
    mock_config.ai_project_endpoint = "https://test-endpoint"
    mock_config.azure_openai_deployment_model = "test-model"
    mock_config.solution_name = "test-solution"
    
    # Set up credential mock
    mock_credential = AsyncMock()
    mock_get_azure_credential_async.return_value = mock_credential
    
    # Set up client mock
    mock_client_instance = AsyncMock()
    mock_agent_definition = MagicMock()
    mock_client_instance.agents.create_agent.return_value = mock_agent_definition
    mock_ai_project_client.return_value = mock_client_instance
    
    result = await ConversationAgentFactory.create_agent(mock_config)
    
    assert result == mock_agent_definition
    mock_ai_project_client.assert_called_once_with(
        credential=mock_credential,
        endpoint="https://test-endpoint"
    )
    mock_client_instance.agents.create_agent.assert_awaited_once_with(
        model="test-model",
        name="KM-ConversationKnowledgeAgent-test-solution",
        instructions=ANY
    )


@pytest.mark.asyncio
@patch("agents.conversation_agent_factory.AIProjectClient", autospec=True)
@patch("agents.conversation_agent_factory.ChatService", autospec=True)
@patch("agents.conversation_agent_factory.get_azure_credential_async", new_callable=AsyncMock)
async def test_delete_agent_instance(
    mock_get_azure_credential_async,
    mock_chat_service,
    mock_ai_project_client
):
    # Set up mock agent and config
    mock_agent = MagicMock()
    mock_agent.id = "agent-id"
    
    mock_config = MagicMock()
    mock_config.ai_project_endpoint = "https://test-endpoint"
    
    # Set up credential mock
    mock_credential = AsyncMock()
    mock_get_azure_credential_async.return_value = mock_credential
    
    # Set up client mock
    mock_client = AsyncMock()
    mock_ai_project_client.return_value = mock_client
    
    # Set up thread cache
    mock_chat_service.thread_cache = {
        "c1": "t1",
        "c2": "t2"
    }
    
    await ConversationAgentFactory._delete_agent_instance(mock_agent, mock_config)
    
    # Verify AI Project Client was created with correct parameters
    mock_ai_project_client.assert_called_once_with(
        credential=mock_credential,
        endpoint="https://test-endpoint"
    )
    
    # Verify threads were deleted
    mock_client.agents.threads.delete.assert_any_call("t1")
    mock_client.agents.threads.delete.assert_any_call("t2")
    assert mock_client.agents.threads.delete.await_count == 2
    
    # Verify agent was deleted
    mock_client.agents.delete_agent.assert_awaited_once_with("agent-id")