import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agent_framework.exceptions import ServiceResponseException
from fastapi import HTTPException, status
from semantic_kernel.exceptions.agent_exceptions import AgentException as RealAgentException



# ---- Patch imports before importing the service under test ----
@patch("helpers.azure_openai_helper.Config")
@patch("semantic_kernel.agents.AzureAIAgentThread")
@patch("azure.ai.agents.models.TruncationObject")
@patch("semantic_kernel.exceptions.agent_exceptions.AgentException")
@patch("openai.AzureOpenAI")
@patch("helpers.utils.format_stream_response")
@pytest.fixture
def patched_imports(mock_format_stream, mock_openai, mock_agent_exception, mock_truncation, mock_thread, mock_config):
    """Apply patches to dependencies before importing ChatService."""
    # Configure mock Config
    mock_config_instance = MagicMock()
    mock_config_instance.azure_openai_endpoint = "https://test.openai.azure.com"
    mock_config_instance.azure_openai_api_version = "2024-02-15-preview"
    mock_config_instance.azure_openai_deployment_model = "gpt-4o-mini"
    mock_config_instance.azure_ai_project_conn_string = "test_conn_string"
    mock_config.return_value = mock_config_instance
    
    # Import the service under test after patching dependencies
    with patch("services.chat_service.Config", mock_config), \
         patch("services.chat_service.AzureAIAgentThread", mock_thread), \
         patch("services.chat_service.TruncationObject", mock_truncation), \
         patch("services.chat_service.AgentException", mock_agent_exception), \
         patch("helpers.azure_openai_helper.openai.AzureOpenAI", mock_openai), \
         patch("services.chat_service.format_stream_response", mock_format_stream):
        from services.chat_service import ChatService, ExpCache
        return ChatService, ExpCache, {
            'config': mock_config,
            'thread': mock_thread,
            'truncation': mock_truncation,
            'agent_exception': mock_agent_exception,
            'openai': mock_openai,
            'format_stream': mock_format_stream
        }


# ---- Import service under test with patches ----
with patch("common.config.config.Config") as mock_config, \
     patch("semantic_kernel.agents.AzureAIAgentThread") as mock_thread, \
     patch("azure.ai.agents.models.TruncationObject") as mock_truncation, \
     patch("semantic_kernel.exceptions.agent_exceptions.AgentException", new=RealAgentException) as mock_agent_exception, \
     patch("openai.AzureOpenAI") as mock_openai, \
     patch("helpers.utils.format_stream_response") as mock_format_stream:
    
    # Configure mock Config
    mock_config_instance = MagicMock()
    mock_config_instance.azure_openai_endpoint = "https://test.openai.azure.com"
    mock_config_instance.azure_openai_api_version = "2024-02-15-preview"
    mock_config_instance.azure_openai_deployment_model = "gpt-4o-mini"
    mock_config_instance.azure_ai_project_conn_string = "test_conn_string"
    mock_config.return_value = mock_config_instance
    
    from services.chat_service import ChatService, ExpCache


@pytest.fixture
def chat_service():
    """Create a ChatService instance for testing."""
    # Reset class-level cache before each test
    ChatService.thread_cache = None
    return ChatService()


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    agent = MagicMock()
    agent.client = MagicMock()
    agent.invoke_stream = AsyncMock()
    return agent


class TestExpCache:
    """Test cases for ExpCache class."""
    
    def test_init(self):
        """Test ExpCache initialization."""
        cache = ExpCache(maxsize=10, ttl=60)
        assert cache.maxsize == 10
        assert cache.ttl == 60
    
    @patch('asyncio.create_task')
    def test_expire(self, mock_create_task):
        """Test expire method."""
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
        """Test popitem method."""
        cache = ExpCache(maxsize=2, ttl=60)
        cache['key1'] = 'thread_id_1'
        cache['key2'] = 'thread_id_2'
        cache['key3'] = 'thread_id_3'  
        
        # Verify thread deletion was scheduled
        mock_create_task.assert_called()


class TestChatService:
    """Test cases for ChatService class."""
    
    @patch("services.chat_service.Config")
    def test_init(self, mock_config_class):
        """Test ChatService initialization."""
        # Configure mock Config
        mock_config_instance = MagicMock()
        mock_config_instance.azure_openai_endpoint = "https://test.openai.azure.com"
        mock_config_instance.azure_openai_api_version = "2024-02-15-preview"
        mock_config_instance.azure_openai_deployment_model = "gpt-4o-mini"
        mock_config_instance.azure_ai_project_conn_string = "test_conn_string"
        mock_config_instance.orchestrator_agent_name = "test-agent"
        mock_config_class.return_value = mock_config_instance
        
        # Reset class-level cache for test isolation
        ChatService.thread_cache = None
        
        service = ChatService()
        
        assert service.azure_openai_deployment_name == "gpt-4o-mini"
        assert ChatService.thread_cache is not None

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection")
    @patch("services.chat_service.ChatAgent")
    @patch("services.chat_service.AzureAIClient")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_success(
        self, mock_credential, mock_project_client_class, mock_azure_client_class, 
        mock_chat_agent_class, mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test successful streaming with valid query."""
        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_cred.close = AsyncMock()
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_openai_client = MagicMock()
        mock_conversation = MagicMock()
        mock_conversation.id = "test-conversation-id"
        mock_openai_client.conversations.create = AsyncMock(return_value=mock_conversation)
        mock_project_client.get_openai_client.return_value = mock_openai_client
        mock_project_client_class.return_value = mock_project_client

        mock_chat_client = MagicMock()
        mock_azure_client_class.return_value = mock_chat_client

        mock_agent = AsyncMock()
        mock_agent.__aenter__ = AsyncMock(return_value=mock_agent)
        mock_agent.__aexit__ = AsyncMock(return_value=None)
        mock_thread = MagicMock()
        mock_agent.get_new_thread.return_value = mock_thread
        
        # Create mock chunks with text
        mock_chunk1 = MagicMock()
        mock_chunk1.text = "Hello"
        mock_chunk1.contents = []
        mock_chunk2 = MagicMock()
        mock_chunk2.text = " World"
        mock_chunk2.contents = []
        
        async def mock_stream(*args, **kwargs):
            yield mock_chunk1
            yield mock_chunk2
        
        mock_agent.run_stream = mock_stream
        mock_chat_agent_class.return_value = mock_agent

        mock_sqldb_conn.return_value = MagicMock()
        mock_tool_instance = MagicMock()
        mock_tool_instance.get_sql_response = MagicMock()
        mock_sql_tool.return_value = mock_tool_instance

        # Execute
        result_chunks = []
        async for chunk in chat_service.stream_openai_text("conv123", "test query"):
            result_chunks.append(chunk)

        # Verify
        assert len(result_chunks) > 0
        assert "Hello" in "".join(result_chunks)

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection")
    @patch("services.chat_service.ChatAgent")
    @patch("services.chat_service.AzureAIClient")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_empty_query(
        self, mock_credential, mock_project_client_class, mock_azure_client_class,
        mock_chat_agent_class, mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test streaming with empty query."""
        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_cred.close = AsyncMock()
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_openai_client = MagicMock()
        mock_conversation = MagicMock()
        mock_conversation.id = "test-conversation-id"
        mock_openai_client.conversations.create = AsyncMock(return_value=mock_conversation)
        mock_project_client.get_openai_client.return_value = mock_openai_client
        mock_project_client_class.return_value = mock_project_client

        mock_chat_client = MagicMock()
        mock_azure_client_class.return_value = mock_chat_client

        mock_agent = AsyncMock()
        mock_agent.__aenter__ = AsyncMock(return_value=mock_agent)
        mock_agent.__aexit__ = AsyncMock(return_value=None)
        mock_thread = MagicMock()
        mock_agent.get_new_thread.return_value = mock_thread
        
        # Create mock chunks
        mock_chunk = MagicMock()
        mock_chunk.text = "query."
        mock_chunk.contents = []
        
        async def mock_stream(*args, **kwargs):
            yield mock_chunk
        
        mock_agent.run_stream = mock_stream
        mock_chat_agent_class.return_value = mock_agent

        mock_sqldb_conn.return_value = MagicMock()
        mock_tool_instance = MagicMock()
        mock_tool_instance.get_sql_response = MagicMock()
        mock_sql_tool.return_value = mock_tool_instance

        # Execute with empty query
        result_chunks = []
        async for chunk in chat_service.stream_openai_text("conv123", ""):
            result_chunks.append(chunk)

        # Verify - should handle empty query gracefully
        assert len(result_chunks) > 0

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection")
    @patch("services.chat_service.ChatAgent")
    @patch("services.chat_service.AzureAIClient")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_with_citations(
        self, mock_credential, mock_project_client_class, mock_azure_client_class,
        mock_chat_agent_class, mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test streaming with citations in response."""
        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_cred.close = AsyncMock()
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_openai_client = MagicMock()
        mock_conversation = MagicMock()
        mock_conversation.id = "test-conversation-id"
        mock_openai_client.conversations.create = AsyncMock(return_value=mock_conversation)
        mock_project_client.get_openai_client.return_value = mock_openai_client
        mock_project_client_class.return_value = mock_project_client

        mock_chat_client = MagicMock()
        mock_azure_client_class.return_value = mock_chat_client

        mock_agent = AsyncMock()
        mock_agent.__aenter__ = AsyncMock(return_value=mock_agent)
        mock_agent.__aexit__ = AsyncMock(return_value=None)
        mock_thread = MagicMock()
        mock_agent.get_new_thread.return_value = mock_thread
        
        # Create mock chunks with citations
        mock_annotation = MagicMock()
        mock_annotation.url = "http://example.com"
        mock_annotation.title = "Test Citation"
        
        mock_content = MagicMock()
        mock_content.annotations = [mock_annotation]
        
        mock_chunk = MagicMock()
        mock_chunk.text = "Answer with citation"
        mock_chunk.contents = [mock_content]
        
        async def mock_stream(*args, **kwargs):
            yield mock_chunk
        
        mock_agent.run_stream = mock_stream
        mock_chat_agent_class.return_value = mock_agent

        mock_sqldb_conn.return_value = MagicMock()

        # Execute
        result_chunks = []
        async for chunk in chat_service.stream_openai_text("conv123", "test query"):
            result_chunks.append(chunk)

        # Verify citations are included
        full_response = "".join(result_chunks)
        assert "citations" in full_response
        assert "http://example.com" in full_response

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection")
    @patch("services.chat_service.ChatAgent")
    @patch("services.chat_service.AzureAIClient")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_rate_limit_error(
        self, mock_credential, mock_project_client_class, mock_azure_client_class,
        mock_chat_agent_class, mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test handling of rate limit errors."""
        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_cred.close = AsyncMock()
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_project_client_class.return_value = mock_project_client

        mock_chat_client = MagicMock()
        mock_azure_client_class.return_value = mock_chat_client

        mock_agent = AsyncMock()
        mock_agent.__aenter__ = AsyncMock(return_value=mock_agent)
        mock_agent.__aexit__ = AsyncMock(
            side_effect=ServiceResponseException("Rate limit is exceeded. Try again in 30 seconds")
        )
        mock_chat_agent_class.return_value = mock_agent

        mock_sqldb_conn.return_value = MagicMock()
        mock_tool_instance = MagicMock()
        mock_tool_instance.get_sql_response = MagicMock()
        mock_sql_tool.return_value = mock_tool_instance

        # Execute and verify exception
        with pytest.raises(ServiceResponseException) as exc_info:
            async for chunk in chat_service.stream_openai_text("conv123", "test query"):
                pass
        
        assert "Rate limit is exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection")
    @patch("services.chat_service.ChatAgent")
    @patch("services.chat_service.AzureAIClient")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_general_exception(
        self, mock_credential, mock_project_client_class, mock_azure_client_class,
        mock_chat_agent_class, mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test handling of general exceptions."""
        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_cred.close = AsyncMock()
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_project_client_class.return_value = mock_project_client

        mock_chat_client = MagicMock()
        mock_azure_client_class.return_value = mock_chat_client

        mock_agent = AsyncMock()
        mock_agent.__aenter__ = AsyncMock(return_value=mock_agent)
        mock_agent.__aexit__ = AsyncMock(side_effect=Exception("General error"))
        mock_chat_agent_class.return_value = mock_agent

        mock_sqldb_conn.return_value = MagicMock()
        mock_tool_instance = MagicMock()
        mock_tool_instance.get_sql_response = MagicMock()
        mock_sql_tool.return_value = mock_tool_instance

        # Execute and verify exception
        with pytest.raises(HTTPException) as exc_info:
            async for chunk in chat_service.stream_openai_text("conv123", "test query"):
                pass
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

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
    async def test_stream_chat_request_rate_limit_exception(self, chat_service):
        """Test stream_chat_request with rate limit exception."""
        # Mock stream_openai_text to raise rate limit error
        async def mock_stream(*args, **kwargs):
            raise ServiceResponseException("Rate limit is exceeded. Try again in 60 seconds.")
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
        assert "Rate limit is exceeded" in error_data["error"]

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

    @pytest.mark.asyncio
    @patch("services.chat_service.SQLTool")
    @patch("services.chat_service.get_sqldb_connection")
    @patch("services.chat_service.ChatAgent")
    @patch("services.chat_service.AzureAIClient")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    async def test_stream_openai_text_with_cached_thread(
        self, mock_credential, mock_project_client_class, mock_azure_client_class,
        mock_chat_agent_class, mock_sqldb_conn, mock_sql_tool, chat_service
    ):
        """Test streaming with cached thread ID."""
        # Pre-populate cache
        ChatService.thread_cache = ExpCache(maxsize=1000, ttl=3600.0)
        ChatService.thread_cache["conv123"] = "cached-thread-id"

        # Setup mocks
        mock_cred = AsyncMock()
        mock_cred.__aenter__ = AsyncMock(return_value=mock_cred)
        mock_cred.__aexit__ = AsyncMock(return_value=None)
        mock_cred.close = AsyncMock()
        mock_credential.return_value = mock_cred

        mock_project_client = MagicMock()
        mock_project_client.__aenter__ = AsyncMock(return_value=mock_project_client)
        mock_project_client.__aexit__ = AsyncMock(return_value=None)
        mock_project_client_class.return_value = mock_project_client

        mock_chat_client = MagicMock()
        mock_azure_client_class.return_value = mock_chat_client

        mock_agent = AsyncMock()
        mock_agent.__aenter__ = AsyncMock(return_value=mock_agent)
        mock_agent.__aexit__ = AsyncMock(return_value=None)
        mock_thread = MagicMock()
        mock_agent.get_new_thread.return_value = mock_thread
        
        mock_chunk = MagicMock()
        mock_chunk.text = "Response"
        mock_chunk.contents = []
        
        async def mock_stream(*args, **kwargs):
            yield mock_chunk
        
        mock_agent.run_stream = mock_stream
        mock_chat_agent_class.return_value = mock_agent

        mock_sqldb_conn.return_value = MagicMock()
        mock_tool_instance = MagicMock()
        mock_tool_instance.get_sql_response = MagicMock()
        mock_sql_tool.return_value = mock_tool_instance

        # Execute
        result_chunks = []
        async for chunk in chat_service.stream_openai_text("conv123", "test query"):
            result_chunks.append(chunk)

        # Verify cached thread was used
        mock_agent.get_new_thread.assert_called_with(service_thread_id="cached-thread-id")
        assert len(result_chunks) > 0

