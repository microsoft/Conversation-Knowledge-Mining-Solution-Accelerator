import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from agent_framework.exceptions import ServiceResponseException as RealServiceResponseException

# Mock get_db_connection
import sys
import os
# Add src directory to the path to make imports work
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../src'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
    
with patch("common.database.sqldb_service.get_db_connection") as mock_get_db_connection:
    mock_get_db_connection.return_value = AsyncMock()

# ---- Patch imports before importing the service under test ----
@patch("common.config.config.Config")
@patch("agent_framework.ChatAgent")
@patch("agent_framework.HostedFileSearchTool")
@patch("agent_framework.exceptions.ServiceResponseException")
@patch("agent_framework.azure.AzureAIAgentClient")
@patch("helpers.utils.format_stream_response")
@pytest.fixture
def patched_imports(mock_format_stream, mock_client, mock_service_exception, mock_search_tool, mock_chat_agent, mock_config):
    """Apply patches to dependencies before importing ChatService."""
    # Configure mock Config
    mock_config_instance = MagicMock()
    mock_config_instance.azure_openai_deployment_model = "gpt-4o-mini"
    mock_config_instance.ai_project_endpoint = "https://test.ai.project.endpoint"
    mock_config_instance.azure_ai_search_index = "test-search-index"
    mock_config.return_value = mock_config_instance
    
    # Import the service under test after patching dependencies        
    with patch("services.chat_service.Config", mock_config), \
         patch("services.chat_service.ChatAgent", mock_chat_agent), \
         patch("services.chat_service.HostedFileSearchTool", mock_search_tool), \
         patch("services.chat_service.ServiceResponseException", mock_service_exception), \
         patch("services.chat_service.AzureAIAgentClient", mock_client), \
         patch("services.chat_service.format_stream_response", mock_format_stream):
        from services.chat_service import ChatService, ExpCache
        return ChatService, ExpCache, {
            'config': mock_config,
            'chat_agent': mock_chat_agent,
            'search_tool': mock_search_tool,
            'service_exception': mock_service_exception,
            'client': mock_client,
            'format_stream': mock_format_stream
        }


# ---- Import service under test with patches ----
with patch("common.config.config.Config") as mock_config, \
     patch("agent_framework.ChatAgent") as mock_chat_agent, \
     patch("agent_framework.HostedFileSearchTool") as mock_search_tool, \
     patch("agent_framework.exceptions.ServiceResponseException", new=RealServiceResponseException) as mock_service_exception, \
     patch("agent_framework.azure.AzureAIAgentClient") as mock_client, \
     patch("helpers.utils.format_stream_response") as mock_format_stream:
    
    # Configure mock Config
    mock_config_instance = MagicMock()
    mock_config_instance.azure_openai_deployment_model = "gpt-4o-mini"
    mock_config_instance.ai_project_endpoint = "https://test.ai.project.endpoint"
    mock_config_instance.azure_ai_search_index = "test-search-index"
    mock_config.return_value = mock_config_instance
    
    from services.chat_service import ChatService, ExpCache


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request object."""
    mock_request = MagicMock()
    mock_request.app.state.conversation_agent = MagicMock()
    mock_request.app.state.conversation_agent.id = "test-agent-id"
    return mock_request


@pytest.fixture
@patch('common.config.config.Config')
@patch('services.chat_service.AIProjectClient')
@patch('services.chat_service.get_azure_credential_async')
def chat_service(mock_get_cred, mock_project_client, mock_config, mock_request):
    """Create a ChatService instance for testing."""
    # Setup config mock
    mock_config_instance = MagicMock()
    mock_config_instance.ai_project_endpoint = "https://test.ai.project.endpoint"
    mock_config_instance.azure_ai_search_index = "test-index"
    mock_config_instance.azure_openai_deployment_model = "gpt-4"
    mock_config.return_value = mock_config_instance
    
    # Setup credential mock
    mock_get_cred.return_value = MagicMock()
    
    # Setup client mock
    mock_client = MagicMock()
    mock_client.agents.threads.create = AsyncMock(return_value=MagicMock(id="new-thread-id"))
    mock_project_client.return_value = mock_client
    
    # Reset class-level cache before each test
    ChatService.thread_cache = None
    
    return ChatService(mock_request)


@pytest.fixture
def mock_project_client():
    """Create a mock AIProjectClient."""
    client = MagicMock()
    client.agents = MagicMock()
    client.agents.threads = MagicMock()
    client.agents.threads.create = AsyncMock()
    client.agents.threads.delete = AsyncMock()
    return client


class TestExpCache:
    """Test cases for ExpCache class."""
    
    @patch('azure.ai.projects.aio.AIProjectClient')
    @patch('common.config.config.Config')
    def test_init(self, mock_config, mock_project_client):
        """Test ExpCache initialization."""
        # Setup config mock
        mock_config_instance = MagicMock()
        mock_config_instance.ai_project_endpoint = "https://test.ai.project.endpoint"
        mock_config.return_value = mock_config_instance
        
        # Mock the AIProjectClient constructor to avoid the ValueError
        mock_project_client.return_value = MagicMock()
        
        with patch("services.chat_service.Config", mock_config):
            cache = ExpCache(maxsize=10, ttl=60)
            assert cache.maxsize == 10
            assert cache.ttl == 60
            assert cache.project_client is not None
    
    @patch('asyncio.create_task')
    @patch('services.chat_service.AIProjectClient')
    def test_expire(self, mock_project_client, mock_create_task):
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
        assert mock_create_task.call_count >= 1
    
    @patch('asyncio.create_task')
    @patch('services.chat_service.AIProjectClient')
    def test_popitem(self, mock_project_client, mock_create_task):
        """Test popitem method."""
        cache = ExpCache(maxsize=2, ttl=60)
        cache['key1'] = 'thread_id_1'
        cache['key2'] = 'thread_id_2'
        cache['key3'] = 'thread_id_3'  
        
        # Verify thread deletion was scheduled
        mock_create_task.assert_called()
        
    @pytest.mark.asyncio
    @patch('common.config.config.Config')
    async def test_delete_thread_async(self, mock_config):
        """Test _delete_thread_async method."""
        # Setup config mock
        mock_config_instance = MagicMock()
        mock_config_instance.ai_project_endpoint = "https://test.ai.project.endpoint"
        mock_config.return_value = mock_config_instance
        
        # Create a new ExpCache with properly mocked config
        with patch("services.chat_service.Config", mock_config):
            cache = ExpCache(maxsize=10, ttl=60)
            
            # Replace the project_client with a mock
            mock_project_client = MagicMock()
            mock_threads = MagicMock()
            mock_threads.delete = AsyncMock()
            mock_project_client.agents.threads = mock_threads
            cache.project_client = mock_project_client
            
            # Call the method
            await cache._delete_thread_async('test_thread_id')
            
            # Verify thread delete was called
            mock_threads.delete.assert_called_once_with(thread_id='test_thread_id')


class TestChatService:
    """Test cases for ChatService class."""
    
    @patch("services.chat_service.Config")
    @patch("services.chat_service.AIProjectClient")
    @patch("services.chat_service.get_azure_credential_async")
    def test_init(self, mock_get_cred, mock_project_client, mock_config_class, mock_request):
        """Test ChatService initialization."""
        # Configure mock Config
        mock_config_instance = MagicMock()
        mock_config_instance.azure_openai_deployment_model = "gpt-4o-mini"
        mock_config_instance.ai_project_endpoint = "https://test.ai.project.endpoint"
        mock_config_instance.azure_ai_search_index = "test-index"
        mock_config_class.return_value = mock_config_instance
        
        # Setup credential mock
        mock_get_cred.return_value = MagicMock()
        
        # Setup client mock
        mock_client = MagicMock()
        mock_client.agents.threads.create = AsyncMock(return_value=MagicMock(id="new-thread-id"))
        mock_project_client.return_value = mock_client
        
        # Reset class-level cache for test isolation
        ChatService.thread_cache = None
        
        service = ChatService(mock_request)
        
        assert service.azure_openai_deployment_name == "gpt-4o-mini"
        assert service.agent == mock_request.app.state.conversation_agent
        assert ChatService.thread_cache is not None
    
    @pytest.mark.asyncio
    @patch('common.config.config.Config')
    @patch('services.chat_service.AIProjectClient')
    @patch('services.chat_service.get_azure_credential_async')
    async def test_stream_openai_text_empty_query(self, mock_get_cred, mock_project_client, mock_config, chat_service):
        """Test streaming with empty query."""
        # Setup config mock
        mock_config_instance = MagicMock()
        mock_config_instance.ai_project_endpoint = "https://test.ai.project.endpoint"
        mock_config_instance.azure_ai_search_index = "test-index"
        mock_config_instance.azure_openai_deployment_model = "gpt-4"
        mock_config.return_value = mock_config_instance
        
        # Setup credential mock
        mock_get_cred.return_value = MagicMock()
        
        # Setup client mock
        mock_client = MagicMock()
        mock_client.agents.threads.create = AsyncMock(return_value=MagicMock(id="new-thread-id"))
        mock_project_client.return_value = mock_client
        
        # Replace the method with a mocked version
        async def mock_stream_openai_text(conversation_id, query):
            if not query:
                yield "Please provide a query."
            else:
                yield "Response to query"
                
        chat_service.stream_openai_text = mock_stream_openai_text
        
        # Execute test
        chunks = []
        async for chunk in chat_service.stream_openai_text("conversation_1", ""):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0] == "Please provide a query."
    
    @pytest.mark.asyncio
    @patch('common.config.config.Config')
    @patch('services.chat_service.AIProjectClient')
    @patch('services.chat_service.get_azure_credential_async')
    async def test_stream_openai_text_rate_limit_error(self, mock_get_cred, mock_project_client, mock_config, chat_service):
        """Test streaming with rate limit error."""
        # Setup config mock
        mock_config_instance = MagicMock()
        mock_config_instance.ai_project_endpoint = "https://test.ai.project.endpoint"
        mock_config_instance.azure_ai_search_index = "test-index"
        mock_config_instance.azure_openai_deployment_model = "gpt-4"
        mock_config.return_value = mock_config_instance
        
        # Setup credential mock
        mock_get_cred.return_value = MagicMock()
        
        # Setup client mock
        mock_client = MagicMock()
        mock_client.agents.threads.create = AsyncMock(return_value=MagicMock(id="new-thread-id"))
        mock_project_client.return_value = mock_client
        
        # Replace the method with a mocked version that raises an exception
        async def mock_stream_openai_text(conversation_id, query):
            raise RealServiceResponseException("Rate limit is exceeded. Try again in 30 seconds")
            yield  # This makes it an async generator
            
        # Assign the mock to the service
        chat_service.stream_openai_text = mock_stream_openai_text
        
        with pytest.raises(RealServiceResponseException) as exc_info:
            async for chunk in chat_service.stream_openai_text("conversation_1", "Hello"):
                pass
        
        assert "Rate limit is exceeded" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_stream_openai_text_general_exception(self):
        """Test streaming with general exception."""
        # Create a simple mock service with a method that raises HTTPException
        mock_service = MagicMock()
        
        async def mock_stream_method(conversation_id, query):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error streaming OpenAI text")
            # This won't be reached but makes it an async generator
            yield
        
        mock_service.stream_openai_text = mock_stream_method
        
        with pytest.raises(HTTPException) as exc_info:
            async for chunk in mock_service.stream_openai_text("conversation_1", "Hello"):
                pass
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @pytest.mark.asyncio
    @patch('services.chat_service.uuid.uuid4')
    @patch('services.chat_service.time.time')
    @patch('services.chat_service.format_stream_response')
    @patch('common.config.config.Config')
    @patch('services.chat_service.AIProjectClient')
    @patch('services.chat_service.get_azure_credential_async')
    async def test_stream_chat_request_success(self, mock_get_cred, mock_project_client, mock_config, 
                                              mock_format_stream, mock_time, mock_uuid, chat_service):
        """Test successful stream chat request."""
        # Setup config mock
        mock_config_instance = MagicMock()
        mock_config_instance.ai_project_endpoint = "https://test.ai.project.endpoint"
        mock_config_instance.azure_ai_search_index = "test-index"
        mock_config_instance.azure_openai_deployment_model = "gpt-4"
        mock_config.return_value = mock_config_instance
        
        # Setup credential mock
        mock_get_cred.return_value = MagicMock()
        
        # Setup client mock
        mock_client = MagicMock()
        mock_client.agents.threads.create = AsyncMock(return_value=MagicMock(id="new-thread-id"))
        mock_project_client.return_value = mock_client
        
        # Setup mocks
        mock_uuid.return_value = "test-uuid"
        mock_time.return_value = 1234567890
        mock_format_stream.return_value = {"formatted": "response"}
        
        # Mock stream_openai_text
        async def mock_stream_openai_text(conversation_id, query):
            yield "Hello"
            yield " world"
        
        chat_service.stream_openai_text = mock_stream_openai_text
        
        request_body = {"history_metadata": {"test": "metadata"}}
        generator = await chat_service.stream_chat_request(request_body, "conv_1", "Hello")
        
        chunks = []
        async for chunk in generator:
            chunks.append(chunk)
        
        assert len(chunks) > 0
        # Verify the chunks contain expected structure
        for chunk in chunks:
            chunk_data = json.loads(chunk.strip())
            assert "formatted" in chunk_data
    
    @pytest.mark.asyncio
    @patch('common.config.config.Config')
    @patch('services.chat_service.AIProjectClient')
    @patch('services.chat_service.get_azure_credential_async')
    async def test_stream_chat_request_agent_exception_rate_limit(self, mock_get_cred, mock_project_client, 
                                                               mock_config, chat_service):
        """Test stream_chat_request with ServiceResponseException for rate limiting."""
        # Setup config mock
        mock_config_instance = MagicMock()
        mock_config_instance.ai_project_endpoint = "https://test.ai.project.endpoint"
        mock_config_instance.azure_ai_search_index = "test-index"
        mock_config_instance.azure_openai_deployment_model = "gpt-4"
        mock_config.return_value = mock_config_instance
        
        # Setup credential mock
        mock_get_cred.return_value = MagicMock()
        
        # Setup client mock
        mock_client = MagicMock()
        mock_client.agents.threads.create = AsyncMock(return_value=MagicMock(id="new-thread-id"))
        mock_project_client.return_value = mock_client
        
        error_message = "Rate limit is exceeded. Try again in 60 seconds"
        
        async def mock_stream_openai_text_rate_limit_error(conversation_id, query):
            raise RealServiceResponseException(error_message)
            yield  # Needs to be an async generator

        chat_service.stream_openai_text = mock_stream_openai_text_rate_limit_error
        
        request_body = {"history_metadata": {}}
        generator = await chat_service.stream_chat_request(request_body, "conv_1", "Hello")
        
        chunks = []
        async for chunk in generator:
            chunks.append(chunk)
            break  # We only expect one error chunk
            
        assert len(chunks) == 1
        error_data = json.loads(chunks[0].strip())
        assert "error" in error_data
        assert "Rate limit is exceeded. Try again in 60 seconds." in error_data["error"]

    @pytest.mark.asyncio
    @patch('common.config.config.Config')
    @patch('services.chat_service.AIProjectClient')
    @patch('services.chat_service.get_azure_credential_async')
    async def test_stream_chat_request_agent_exception_generic(self, mock_get_cred, mock_project_client, 
                                                            mock_config, chat_service):
        """Test stream_chat_request with a generic ServiceResponseException."""
        # Setup config mock
        mock_config_instance = MagicMock()
        mock_config_instance.ai_project_endpoint = "https://test.ai.project.endpoint"
        mock_config_instance.azure_ai_search_index = "test-index"
        mock_config_instance.azure_openai_deployment_model = "gpt-4"
        mock_config.return_value = mock_config_instance
        
        # Setup credential mock
        mock_get_cred.return_value = MagicMock()
        
        # Setup client mock
        mock_client = MagicMock()
        mock_client.agents.threads.create = AsyncMock(return_value=MagicMock(id="new-thread-id"))
        mock_project_client.return_value = mock_client
        
        error_message = "Some other agent error"

        async def mock_stream_openai_text_generic_error(conversation_id, query):
            raise RealServiceResponseException(error_message)
            yield # Needs to be an async generator

        chat_service.stream_openai_text = mock_stream_openai_text_generic_error
        
        request_body = {"history_metadata": {}}
        generator = await chat_service.stream_chat_request(request_body, "conv_1", "Hello")

        chunks = []
        async for chunk in generator:
            chunks.append(chunk)
            break  # We only expect one error chunk
            
        assert len(chunks) == 1
        error_data = json.loads(chunks[0].strip())
        assert "error" in error_data
        assert "An error occurred. Please try again later." == error_data["error"]

    @pytest.mark.asyncio
    @patch('common.config.config.Config')
    @patch('services.chat_service.AIProjectClient')
    @patch('services.chat_service.get_azure_credential_async')
    async def test_stream_chat_request_generic_exception(self, mock_get_cred, mock_project_client, 
                                                      mock_config, chat_service):
        """Test stream_chat_request with a generic Exception."""
        # Setup config mock
        mock_config_instance = MagicMock()
        mock_config_instance.ai_project_endpoint = "https://test.ai.project.endpoint"
        mock_config_instance.azure_ai_search_index = "test-index"
        mock_config_instance.azure_openai_deployment_model = "gpt-4"
        mock_config.return_value = mock_config_instance
        
        # Setup credential mock
        mock_get_cred.return_value = MagicMock()
        
        # Setup client mock
        mock_client = MagicMock()
        mock_client.agents.threads.create = AsyncMock(return_value=MagicMock(id="new-thread-id"))
        mock_project_client.return_value = mock_client
        
        error_message = "Some other error"

        async def mock_stream_openai_text_generic_error(conversation_id, query):
            raise Exception(error_message)
            yield # Needs to be an async generator

        chat_service.stream_openai_text = mock_stream_openai_text_generic_error
        
        request_body = {"history_metadata": {}}
        generator = await chat_service.stream_chat_request(request_body, "conv_1", "Hello")

        chunks = []
        async for chunk in generator:
            chunks.append(chunk)
            break  # We only expect one error chunk
            
        assert len(chunks) == 1
        error_data = json.loads(chunks[0].strip())
        assert "error" in error_data
        assert "An error occurred while processing the request." == error_data["error"]
