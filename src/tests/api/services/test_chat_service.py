import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from services.chat_service import ChatService, ExpCache


@pytest.fixture
def chat_service():
    """Create a ChatService instance for testing."""
    with patch("services.chat_service.Config") as mock_config:
        mock_config_instance = MagicMock()
        mock_config_instance.azure_openai_deployment_model = "gpt-4o-mini"
        mock_config_instance.orchestrator_agent_name = "test-orchestrator"
        mock_config_instance.azure_client_id = "test-client-id"
        mock_config_instance.ai_project_endpoint = "https://test.endpoint.com"
        mock_config.return_value = mock_config_instance
        
        service = ChatService()
        # Reset cache for each test
        service.get_thread_cache().clear()
        yield service


class TestExpCache:
    """Test cases for ExpCache class."""
    
    def test_init(self):
        """Test ExpCache initialization."""
        cache = ExpCache(maxsize=10, ttl=60)
        assert cache.maxsize == 10
        assert cache.ttl == 60
    
    @patch('asyncio.create_task')
    def test_expire(self, mock_create_task):
        """Test expire method schedules thread deletion."""
        cache = ExpCache(maxsize=2, ttl=0.01)
        cache['key1'] = 'thread_id_1'
        cache['key2'] = 'thread_id_2'
        
        # Wait for expiration
        time.sleep(0.02)
        
        # Trigger expiration
        expired_items = cache.expire()
        
        # Verify threads were scheduled for deletion
        assert len(expired_items) == 2
        assert mock_create_task.call_count == 2
    
    @patch('asyncio.create_task')
    def test_popitem(self, mock_create_task):
        """Test popitem method schedules thread deletion."""
        cache = ExpCache(maxsize=2, ttl=60)
        cache['key1'] = 'thread_id_1'
        cache['key2'] = 'thread_id_2'
        cache['key3'] = 'thread_id_3'  # This will trigger LRU eviction
        
        # Verify thread deletion was scheduled
        mock_create_task.assert_called()
    
    @pytest.mark.asyncio
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    @patch("services.chat_service.Config")
    async def test_delete_thread_async_success(self, mock_config, mock_credential, mock_project_client_class):
        """Test successful thread deletion."""
        # Setup mocks
        mock_config_instance = MagicMock()
        mock_config_instance.azure_client_id = "test-client-id"
        mock_config_instance.ai_project_endpoint = "https://test.endpoint.com"
        mock_config.return_value = mock_config_instance
        
        mock_cred = AsyncMock()
        mock_cred.close = AsyncMock()
        mock_credential.return_value = mock_cred
        
        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_openai_client = MagicMock()
        mock_openai_client.conversations.delete = AsyncMock()
        mock_project_client.get_openai_client.return_value = mock_openai_client
        mock_project_client_class.return_value = mock_project_client
        
        # Execute
        cache = ExpCache(maxsize=10, ttl=60)
        await cache._delete_thread_async("thread_id_123")
        
        # Verify
        mock_openai_client.conversations.delete.assert_called_once_with(conversation_id="thread_id_123")
        mock_cred.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    @patch("services.chat_service.Config")
    async def test_delete_thread_async_with_exception(self, mock_config, mock_credential, mock_project_client_class):
        """Test thread deletion handles exceptions gracefully."""
        # Setup mocks
        mock_config_instance = MagicMock()
        mock_config_instance.azure_client_id = "test-client-id"
        mock_config_instance.ai_project_endpoint = "https://test.endpoint.com"
        mock_config.return_value = mock_config_instance
        
        mock_cred = AsyncMock()
        mock_cred.close = AsyncMock()
        mock_credential.return_value = mock_cred
        
        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_openai_client = MagicMock()
        mock_openai_client.conversations.delete = AsyncMock(side_effect=Exception("Deletion failed"))
        mock_project_client.get_openai_client.return_value = mock_openai_client
        mock_project_client_class.return_value = mock_project_client
        
        # Execute - should not raise exception
        cache = ExpCache(maxsize=10, ttl=60)
        await cache._delete_thread_async("thread_id_123")
        
        # Verify credential is still closed even on error
        mock_cred.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("services.chat_service.Config")
    async def test_delete_thread_async_empty_thread_id(self, mock_config):
        """Test thread deletion with empty thread ID."""
        # Setup mocks
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        
        # Execute - should handle gracefully
        cache = ExpCache(maxsize=10, ttl=60)
        await cache._delete_thread_async("")
        await cache._delete_thread_async(None)


class TestChatService:
    """Test cases for ChatService class."""
    
    @patch("services.chat_service.Config")
    def test_init(self, mock_config_class):
        """Test ChatService initialization."""
        # Configure mock Config
        mock_config_instance = MagicMock()
        mock_config_instance.azure_openai_deployment_model = "gpt-4o-mini"
        mock_config_instance.orchestrator_agent_name = "test-orchestrator"
        mock_config_instance.azure_client_id = "test-client-id"
        mock_config_instance.ai_project_endpoint = "https://test.endpoint.com"
        mock_config_class.return_value = mock_config_instance
        
        service = ChatService()
        
        assert service.azure_openai_deployment_name == "gpt-4o-mini"
        assert service.orchestrator_agent_name == "test-orchestrator"
        assert service.azure_client_id == "test-client-id"
        assert service.ai_project_endpoint == "https://test.endpoint.com"
    
    def test_get_thread_cache(self, chat_service):
        """Test get_thread_cache creates and returns cache."""
        cache = chat_service.get_thread_cache()
        assert cache is not None
        assert isinstance(cache, ExpCache)
        
        # Verify same instance is returned
        cache2 = chat_service.get_thread_cache()
        assert cache is cache2

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection")
    @patch("services.chat_service.AzureAIProjectAgentProvider")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_success(
        self, mock_credential, mock_project_client_class, mock_provider_class,
        mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test successful streaming with valid query."""
        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_openai_client = MagicMock()
        mock_conversation = MagicMock()
        mock_conversation.id = "test-thread-id"
        mock_openai_client.conversations.create = AsyncMock(return_value=mock_conversation)
        mock_project_client.get_openai_client.return_value = mock_openai_client
        mock_project_client_class.return_value = mock_project_client

        # Mock agent and provider
        mock_agent = MagicMock()
        mock_chunk1 = MagicMock()
        mock_chunk1.text = "Hello"
        mock_chunk1.contents = []
        mock_chunk2 = MagicMock()
        mock_chunk2.text = " World"
        mock_chunk2.contents = []
        
        async def mock_run(*args, **kwargs):
            yield mock_chunk1
            yield mock_chunk2
        
        mock_agent.run = mock_run
        
        mock_provider = MagicMock()
        mock_provider.get_agent = AsyncMock(return_value=mock_agent)
        mock_provider_class.return_value = mock_provider

        mock_sqldb_conn.return_value = AsyncMock()
        mock_tool_instance = MagicMock()
        mock_tool_instance.get_sql_response = MagicMock()
        mock_sql_tool.return_value = mock_tool_instance

        # Execute
        result_chunks = []
        async for chunk in chat_service.stream_openai_text("conv123", "test query"):
            result_chunks.append(chunk)

        # Verify
        assert len(result_chunks) > 0
        full_response = "".join(result_chunks)
        assert "Hello" in full_response
        assert "World" in full_response
        assert "citations" in full_response

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection")
    @patch("services.chat_service.AzureAIProjectAgentProvider")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_empty_query(
        self, mock_credential, mock_project_client_class, mock_provider_class,
        mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test streaming with empty query - should use default query."""
        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_openai_client = MagicMock()
        mock_conversation = MagicMock()
        mock_conversation.id = "test-thread-id"
        mock_openai_client.conversations.create = AsyncMock(return_value=mock_conversation)
        mock_project_client.get_openai_client.return_value = mock_openai_client
        mock_project_client_class.return_value = mock_project_client

        # Mock agent
        mock_agent = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.text = "Response"
        mock_chunk.contents = []
        
        async def mock_run(query, *args, **kwargs):
            # Verify default query was used
            assert query == "Please provide a query."
            yield mock_chunk
        
        mock_agent.run = mock_run
        
        mock_provider = MagicMock()
        mock_provider.get_agent = AsyncMock(return_value=mock_agent)
        mock_provider_class.return_value = mock_provider

        mock_sqldb_conn.return_value = AsyncMock()
        mock_tool_instance = MagicMock()
        mock_tool_instance.get_sql_response = MagicMock()
        mock_sql_tool.return_value = mock_tool_instance

        # Execute with empty query
        result_chunks = []
        async for chunk in chat_service.stream_openai_text("conv123", ""):
            result_chunks.append(chunk)

        # Verify
        assert len(result_chunks) > 0

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection")
    @patch("services.chat_service.AzureAIProjectAgentProvider")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_with_citations(
        self, mock_credential, mock_project_client_class, mock_provider_class,
        mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test streaming with citations in response."""
        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_openai_client = MagicMock()
        mock_conversation = MagicMock()
        mock_conversation.id = "test-thread-id"
        mock_openai_client.conversations.create = AsyncMock(return_value=mock_conversation)
        mock_project_client.get_openai_client.return_value = mock_openai_client
        mock_project_client_class.return_value = mock_project_client

        # Mock agent with citations
        mock_agent = MagicMock()
        
        # Create citation
        mock_annotation = MagicMock()
        mock_annotation.get = MagicMock(side_effect=lambda k, d=None: {
            'title': 'Test Documentation',
            'additional_properties': {'get_url': 'http://example.com/doc'}
        }.get(k, d))
        
        mock_content = MagicMock()
        mock_content.annotations = [mock_annotation]
        
        mock_chunk = MagicMock()
        mock_chunk.text = "Answer with citation"
        mock_chunk.contents = [mock_content]
        
        async def mock_run(*args, **kwargs):
            yield mock_chunk
        
        mock_agent.run = mock_run
        
        mock_provider = MagicMock()
        mock_provider.get_agent = AsyncMock(return_value=mock_agent)
        mock_provider_class.return_value = mock_provider

        mock_sqldb_conn.return_value = AsyncMock()
        mock_tool_instance = MagicMock()
        mock_tool_instance.get_sql_response = MagicMock()
        mock_sql_tool.return_value = mock_tool_instance

        # Execute
        result_chunks = []
        async for chunk in chat_service.stream_openai_text("conv123", "test query"):
            result_chunks.append(chunk)

        # Verify citations are included
        full_response = "".join(result_chunks)
        assert "citations" in full_response
        assert "Test Documentation" in full_response
        assert "http://example.com/doc" in full_response

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection")
    @patch("services.chat_service.AzureAIProjectAgentProvider")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_with_citation_markers(
        self, mock_credential, mock_project_client_class, mock_provider_class,
        mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test streaming replaces citation markers correctly."""
        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_openai_client = MagicMock()
        mock_conversation = MagicMock()
        mock_conversation.id = "test-thread-id"
        mock_openai_client.conversations.create = AsyncMock(return_value=mock_conversation)
        mock_project_client.get_openai_client.return_value = mock_openai_client
        mock_project_client_class.return_value = mock_project_client

        # Mock agent with citation markers
        mock_agent = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.text = "Answer 【4:0†source1】 with 【5:1†source2】 citations"
        mock_chunk.contents = []
        
        async def mock_run(*args, **kwargs):
            yield mock_chunk
        
        mock_agent.run = mock_run
        
        mock_provider = MagicMock()
        mock_provider.get_agent = AsyncMock(return_value=mock_agent)
        mock_provider_class.return_value = mock_provider

        mock_sqldb_conn.return_value = AsyncMock()
        mock_tool_instance = MagicMock()
        mock_tool_instance.get_sql_response = MagicMock()
        mock_sql_tool.return_value = mock_tool_instance

        # Execute
        result_chunks = []
        async for chunk in chat_service.stream_openai_text("conv123", "test query"):
            result_chunks.append(chunk)

        # Verify citation markers are replaced with [1], [2], etc.
        full_response = "".join(result_chunks)
        assert "[1]" in full_response
        assert "[2]" in full_response
        assert "【" not in full_response  # Original markers should be replaced

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection")
    @patch("services.chat_service.AzureAIProjectAgentProvider")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_cached_thread(
        self, mock_credential, mock_project_client_class, mock_provider_class,
        mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test streaming with cached thread ID."""
        # Pre-populate cache
        cache = chat_service.get_thread_cache()
        cache["conv123"] = "cached-thread-id"

        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_openai_client = MagicMock()
        mock_openai_client.conversations.create = AsyncMock()
        mock_project_client.get_openai_client.return_value = mock_openai_client
        mock_project_client_class.return_value = mock_project_client

        # Mock agent
        mock_agent = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.text = "Response"
        mock_chunk.contents = []
        
        async def mock_run(query, stream=False, conversation_id=None):
            # Verify cached thread ID is used
            assert conversation_id == "cached-thread-id"
            yield mock_chunk
        
        mock_agent.run = mock_run
        
        mock_provider = MagicMock()
        mock_provider.get_agent = AsyncMock(return_value=mock_agent)
        mock_provider_class.return_value = mock_provider

        mock_sqldb_conn.return_value = AsyncMock()
        mock_tool_instance = MagicMock()
        mock_tool_instance.get_sql_response = MagicMock()
        mock_sql_tool.return_value = mock_tool_instance

        # Execute
        result_chunks = []
        async for chunk in chat_service.stream_openai_text("conv123", "test query"):
            result_chunks.append(chunk)

        # Verify cached thread was used (no new conversation created)
        mock_openai_client.conversations.create.assert_not_called()
        assert len(result_chunks) > 0

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection", new_callable=AsyncMock)
    @patch("services.chat_service.AzureAIProjectAgentProvider")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_rate_limit_error(
        self, mock_credential, mock_project_client_class, mock_provider_class,
        mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test handling of rate limit errors."""
        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_openai_client = MagicMock()
        mock_conversation = MagicMock()
        mock_conversation.id = "test-thread-id"
        mock_openai_client.conversations.create = AsyncMock(return_value=mock_conversation)
        mock_project_client.get_openai_client.return_value = mock_openai_client
        mock_project_client_class.return_value = mock_project_client

        # Mock SQLTool connection - mock_sqldb_conn is already AsyncMock
        mock_conn = MagicMock()
        mock_sqldb_conn.return_value = mock_conn
        mock_tool_instance = MagicMock()
        mock_tool_instance.get_sql_response = MagicMock()
        mock_sql_tool.return_value = mock_tool_instance

        # Mock agent that raises rate limit error (matches service's detection logic)
        mock_agent = MagicMock()
        
        async def mock_run(*args, **kwargs):
            raise Exception("Error 429: Too many requests, please try again later")
            yield  # Make it an async generator
        
        mock_agent.run = mock_run
        
        mock_provider = MagicMock()
        mock_provider.get_agent = AsyncMock(return_value=mock_agent)
        mock_provider_class.return_value = mock_provider

        # Execute and verify HTTPException with 429 status
        with pytest.raises(HTTPException) as exc_info:
            async for chunk in chat_service.stream_openai_text("conv123", "test query"):
                pass
        
        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "high demand" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection")
    @patch("services.chat_service.AzureAIProjectAgentProvider")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_general_exception(
        self, mock_credential, mock_project_client_class, mock_provider_class,
        mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test handling of general exceptions."""
        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_project_client_class.return_value = mock_project_client

        # Mock agent that raises general error
        mock_agent = MagicMock()
        
        async def mock_run(*args, **kwargs):
            raise Exception("General error")
            yield
        
        mock_agent.run = mock_run
        
        mock_provider = MagicMock()
        mock_provider.get_agent = AsyncMock(return_value=mock_agent)
        mock_provider_class.return_value = mock_provider

        mock_sqldb_conn.return_value = AsyncMock()
        mock_tool_instance = MagicMock()
        mock_tool_instance.get_sql_response = MagicMock()
        mock_sql_tool.return_value = mock_tool_instance

        # Execute and verify HTTPException with 500 status
        with pytest.raises(HTTPException) as exc_info:
            async for chunk in chat_service.stream_openai_text("conv123", "test query"):
                pass
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection")
    @patch("services.chat_service.AzureAIProjectAgentProvider")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_no_response(
        self, mock_credential, mock_project_client_class, mock_provider_class,
        mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test handling when agent returns no text."""
        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_openai_client = MagicMock()
        mock_conversation = MagicMock()
        mock_conversation.id = "test-thread-id"
        mock_openai_client.conversations.create = AsyncMock(return_value=mock_conversation)
        mock_project_client.get_openai_client.return_value = mock_openai_client
        mock_project_client_class.return_value = mock_project_client

        # Mock agent with empty response
        mock_agent = MagicMock()
        
        async def mock_run(*args, **kwargs):
            # Return chunks with no text
            mock_chunk = MagicMock()
            mock_chunk.text = None
            mock_chunk.contents = []
            yield mock_chunk
        
        mock_agent.run = mock_run
        
        mock_provider = MagicMock()
        mock_provider.get_agent = AsyncMock(return_value=mock_agent)
        mock_provider_class.return_value = mock_provider

        mock_sqldb_conn.return_value = AsyncMock()
        mock_tool_instance = MagicMock()
        mock_tool_instance.get_sql_response = MagicMock()
        mock_sql_tool.return_value = mock_tool_instance

        # Execute
        result_chunks = []
        async for chunk in chat_service.stream_openai_text("conv123", "test query"):
            result_chunks.append(chunk)

        # Verify fallback message is provided
        full_response = "".join(result_chunks)
        assert "cannot answer" in full_response.lower() or "citations" in full_response

    @pytest.mark.asyncio
    async def test_stream_chat_request_success(self, chat_service):
        """Test successful stream_chat_request."""
        # Mock stream_openai_text to return chunks
        async def mock_stream(*args, **kwargs):
            yield '{ "answer": "Hello'
            yield ' World'
            yield ', "citations": []}'
        
        chat_service.stream_openai_text = mock_stream

        # Execute
        generator = await chat_service.stream_chat_request("conv123", "test query")
        
        chunks = []
        async for chunk in generator:
            chunks.append(chunk)

        # Verify
        assert len(chunks) > 0
        for chunk in chunks:
            data = json.loads(chunk.strip())
            assert "choices" in data
            assert isinstance(data["choices"], list)

    @pytest.mark.asyncio
    async def test_stream_chat_request_http_exception(self, chat_service):
        """Test stream_chat_request with HTTPException."""
        # Mock stream_openai_text to raise HTTPException
        async def mock_stream(*args, **kwargs):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
            yield
        
        chat_service.stream_openai_text = mock_stream

        # Execute
        generator = await chat_service.stream_chat_request("conv123", "test query")
        
        chunks = []
        async for chunk in generator:
            chunks.append(chunk)

        # Verify error response
        assert len(chunks) == 1
        error_data = json.loads(chunks[0].strip())
        assert "error" in error_data
        assert "Rate limit exceeded" in error_data["error"]

    @pytest.mark.asyncio
    async def test_stream_chat_request_generic_exception(self, chat_service):
        """Test stream_chat_request with generic exception."""
        # Mock stream_openai_text to raise generic error
        async def mock_stream(*args, **kwargs):
            raise Exception("Unexpected error")
            yield
        
        chat_service.stream_openai_text = mock_stream

        # Execute
        generator = await chat_service.stream_chat_request("conv123", "test query")
        
        chunks = []
        async for chunk in generator:
            chunks.append(chunk)

        # Verify error response
        assert len(chunks) == 1
        error_data = json.loads(chunks[0].strip())
        assert "error" in error_data
        assert "An error occurred while processing the request" in error_data["error"]
