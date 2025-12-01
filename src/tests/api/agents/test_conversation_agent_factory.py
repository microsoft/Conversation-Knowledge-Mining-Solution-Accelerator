import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from agents.conversation_agent_factory import ConversationAgentFactory


@pytest.fixture(autouse=True)
def reset_conversation_agent_factory():
    ConversationAgentFactory._agent = None
    yield
    ConversationAgentFactory._agent = None


@pytest.mark.asyncio
@patch("agents.conversation_agent_factory.AzureAIAgentSettings", autospec=True)
@patch("agents.conversation_agent_factory.AzureAIAgent", autospec=True)
@patch("agents.conversation_agent_factory.get_azure_credential_async", new_callable=AsyncMock)
async def test_get_agent_creates_new_instance(
    mock_get_azure_credential_async,
    mock_azure_agent,
    mock_azure_ai_agent_settings
):
    mock_settings = MagicMock()
    mock_settings.endpoint = "https://test-endpoint"
    mock_settings.model_deployment_name = "test-model"
    mock_azure_ai_agent_settings.return_value = mock_settings

    mock_credential = AsyncMock()
    mock_get_azure_credential_async.return_value = mock_credential

    mock_client = AsyncMock()
    mock_agent_definition = MagicMock()
    mock_client.agents.create_agent.return_value = mock_agent_definition
    mock_azure_agent.create_client.return_value = mock_client

    agent_instance = MagicMock()
    mock_azure_agent.return_value = agent_instance

    result = await ConversationAgentFactory.get_agent()

    assert result == agent_instance
    mock_azure_agent.create_client.assert_called_once_with(
        credential=mock_get_azure_credential_async.return_value,
        endpoint="https://test-endpoint"
    )
    mock_client.agents.create_agent.assert_awaited_once()
    mock_azure_agent.assert_called_once()


@pytest.mark.asyncio
async def test_get_agent_returns_existing_instance():
    ConversationAgentFactory._agent = MagicMock()
    result = await ConversationAgentFactory.get_agent()
    assert result == ConversationAgentFactory._agent


@pytest.mark.asyncio
@patch("agents.conversation_agent_factory.AzureAIAgentThread", autospec=True)
@patch("agents.conversation_agent_factory.ChatService", autospec=True)
async def test_delete_agent_deletes_threads_and_agent(
    mock_chat_service,
    mock_agent_thread
):
    mock_client = AsyncMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-id"
    mock_agent.client = mock_client
    ConversationAgentFactory._agent = mock_agent

    mock_chat_service.thread_cache = {
        "c1": "t1",
        "c2": "t2"
    }

    thread_mock = AsyncMock()
    mock_agent_thread.side_effect = lambda client, thread_id: thread_mock

    await ConversationAgentFactory.delete_agent()

    mock_agent_thread.assert_any_call(client=mock_client, thread_id="t1")
    mock_agent_thread.assert_any_call(client=mock_client, thread_id="t2")
    assert thread_mock.delete.await_count == 2
    mock_client.agents.delete_agent.assert_awaited_once_with("agent-id")
    assert ConversationAgentFactory._agent is None


@pytest.mark.asyncio
@patch("agents.conversation_agent_factory.ChatService", autospec=True)
async def test_delete_agent_handles_missing_thread_cache(mock_chat_service):
    mock_client = AsyncMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-id"
    mock_agent.client = mock_client
    ConversationAgentFactory._agent = mock_agent

    del mock_chat_service.thread_cache  # Simulate absence

    await ConversationAgentFactory.delete_agent()

    mock_client.agents.delete_agent.assert_awaited_once_with("agent-id")
    assert ConversationAgentFactory._agent is None


@pytest.mark.asyncio
async def test_delete_agent_does_nothing_if_none():
    ConversationAgentFactory._agent = None
    await ConversationAgentFactory.delete_agent()
