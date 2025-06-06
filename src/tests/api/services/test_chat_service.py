import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from semantic_kernel.exceptions.agent_exceptions import AgentException as RealAgentException



# ---- Patch imports before importing the service under test ----
@patch("common.config.config.Config")
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
         patch("services.chat_service.openai.AzureOpenAI", mock_openai), \
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
def mock_request():
    """Create a mock FastAPI Request object."""
    mock_request = MagicMock()
    mock_request.app.state.agent = MagicMock()
    mock_request.app.state.agent.client = MagicMock()
    mock_request.app.state.agent.invoke_stream = AsyncMock()
    return mock_request


@pytest.fixture
def chat_service(mock_request):
    """Create a ChatService instance for testing."""
    # Reset class-level cache before each test
    ChatService.thread_cache = None
    return ChatService(mock_request)


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    agent = MagicMock()
    agent.client = MagicMock()
    agent.invoke_stream = AsyncMock()
    return agent


class TestExpCache:
    """Test cases for ExpCache class."""
    
    def test_init_with_agent(self, mock_agent):
        """Test ExpCache initialization with agent."""
        cache = ExpCache(maxsize=10, ttl=60, agent=mock_agent)
        assert cache.agent == mock_agent
        assert cache.maxsize == 10
        assert cache.ttl == 60
    
    def test_init_without_agent(self):
        """Test ExpCache initialization without agent."""
        cache = ExpCache(maxsize=10, ttl=60)
        assert cache.agent is None
    
    @patch('asyncio.create_task')
    @patch('services.chat_service.AzureAIAgentThread')
    def test_expire_with_agent(self, mock_thread_class, mock_create_task, mock_agent):
        """Test expire method when agent is present."""
        cache = ExpCache(maxsize=2, ttl=0.01, agent=mock_agent)
        cache['key1'] = 'thread_id_1'
        cache['key2'] = 'thread_id_2'
        
        # Wait for expiration
        time.sleep(0.02)
        
        # Trigger expiration
        expired_items = cache.expire()
        
        # Verify threads were scheduled for deletion
        assert len(expired_items) == 2
        assert mock_create_task.call_count == 2
    
    def test_expire_without_agent(self):
        """Test expire method when agent is None."""
        cache = ExpCache(maxsize=2, ttl=0.01, agent=None)
        cache['key1'] = 'thread_id_1'
        
        # Wait for expiration
        time.sleep(0.02)
        
        # Should not raise error
        expired_items = cache.expire()
        assert len(expired_items) == 1
    
    @patch('asyncio.create_task')
    @patch('services.chat_service.AzureAIAgentThread')
    def test_popitem_with_agent(self, mock_thread_class, mock_create_task, mock_agent):
        """Test popitem method when agent is present."""
        cache = ExpCache(maxsize=2, ttl=60, agent=mock_agent)
        cache['key1'] = 'thread_id_1'
        cache['key2'] = 'thread_id_2'
        cache['key3'] = 'thread_id_3'  # This should trigger LRU eviction
        
        # Verify thread deletion was scheduled
        mock_create_task.assert_called()


class TestChatService:
    """Test cases for ChatService class."""
    
    @patch("services.chat_service.Config")
    def test_init(self, mock_config_class, mock_request):
        """Test ChatService initialization."""
        # Configure mock Config
        mock_config_instance = MagicMock()
        mock_config_instance.azure_openai_endpoint = "https://test.openai.azure.com"
        mock_config_instance.azure_openai_api_version = "2024-02-15-preview"
        mock_config_instance.azure_openai_deployment_model = "gpt-4o-mini"
        mock_config_instance.azure_ai_project_conn_string = "test_conn_string"
        mock_config_class.return_value = mock_config_instance
        
        # Reset class-level cache for test isolation
        ChatService.thread_cache = None
        
        service = ChatService(mock_request)
        
        assert service.azure_openai_endpoint == "https://test.openai.azure.com"
        assert service.azure_openai_api_version == "2024-02-15-preview"
        assert service.azure_openai_deployment_name == "gpt-4o-mini"
        assert service.agent == mock_request.app.state.agent
        assert ChatService.thread_cache is not None
    
    @patch('services.chat_service.openai.AzureOpenAI')
    def test_process_rag_response_success(self, mock_openai_class, chat_service):
        """Test successful RAG response processing."""
        # Setup mock OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = '{"type": "bar", "data": {"labels": ["A", "B"], "datasets": [{"data": [1, 2]}]}}'
        mock_client.chat.completions.create.return_value = mock_completion
        
        result = chat_service.process_rag_response("Sample RAG response with numbers 10, 20", "Query about data")
        
        assert result["type"] == "bar"
        assert "data" in result
        assert result["data"]["labels"] == ["A", "B"]
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('services.chat_service.openai.AzureOpenAI')
    def test_process_rag_response_invalid_json(self, mock_openai_class, chat_service):
        """Test RAG response processing with invalid JSON."""
        # Setup mock OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = 'Invalid JSON response'
        mock_client.chat.completions.create.return_value = mock_completion
        
        result = chat_service.process_rag_response("Sample RAG response", "Query")
        
        assert "error" in result
        assert result["error"] == "Chart could not be generated from this data. Please ask a different question."
    
    @patch('services.chat_service.openai.AzureOpenAI')
    def test_process_rag_response_exception(self, mock_openai_class, chat_service):
        """Test RAG response processing with exception."""
        # Setup mock to raise exception
        mock_openai_class.side_effect = Exception("OpenAI API error")
        
        result = chat_service.process_rag_response("Sample RAG response", "Query")
        
        assert "error" in result
        assert result["error"] == "Chart could not be generated from this data. Please ask a different question."
    
    @pytest.mark.asyncio
    @patch('services.chat_service.AzureAIAgentThread')
    @patch('services.chat_service.TruncationObject')
    async def test_stream_openai_text_success(self, mock_truncation_class, mock_thread_class, chat_service):
        """Test successful streaming OpenAI text."""
        # Setup mocks
        mock_thread = MagicMock()
        mock_thread.id = "test_thread_id"
        mock_thread_class.return_value = mock_thread
        
        mock_truncation = MagicMock()
        mock_truncation_class.return_value = mock_truncation
        
        # Setup agent response
        mock_response = MagicMock()
        mock_response.content = "Hello, world!"
        mock_response.thread.id = "new_thread_id"
        
        async def mock_invoke_stream(*args, **kwargs):
            yield mock_response
        
        chat_service.agent.invoke_stream = mock_invoke_stream
        
        # Test streaming
        chunks = []
        async for chunk in chat_service.stream_openai_text("conversation_1", "Hello"):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0] == "Hello, world!"
        assert ChatService.thread_cache["conversation_1"] == "new_thread_id"
    
    @pytest.mark.asyncio
    @patch('services.chat_service.AzureAIAgentThread')
    @patch('services.chat_service.TruncationObject')
    async def test_stream_openai_text_empty_query(self, mock_truncation_class, mock_thread_class, chat_service):
        """Test streaming with empty query."""
        mock_response = MagicMock()
        mock_response.content = "Please provide a query."
        mock_response.thread.id = "thread_id"
        
        async def mock_invoke_stream(*args, **kwargs):
            yield mock_response
        
        chat_service.agent.invoke_stream = mock_invoke_stream
        
        chunks = []
        async for chunk in chat_service.stream_openai_text("conversation_1", ""):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0] == "Please provide a query."
    
    @pytest.mark.asyncio
    @patch('services.chat_service.AgentException')
    async def test_stream_openai_text_rate_limit_error(self, mock_agent_exception_class, chat_service):
        """Test streaming with rate limit error."""
        # Setup agent to raise RuntimeError with rate limit message
        async def mock_invoke_stream(*args, **kwargs):
            raise RuntimeError("Rate limit is exceeded. Try again in 30 seconds")
            yield
        
        chat_service.agent.invoke_stream = mock_invoke_stream
        mock_agent_exception_class.side_effect = lambda msg: Exception(msg)
        
        with pytest.raises(Exception) as exc_info:
            async for chunk in chat_service.stream_openai_text("conversation_1", "Hello"):
                pass
        
        assert "Rate limit is exceeded" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_stream_openai_text_general_exception(self, chat_service):
        """Test streaming with general exception."""
        # Setup agent to raise general exception
        async def mock_invoke_stream(*args, **kwargs):
            raise Exception("General error")
        
        chat_service.agent.invoke_stream = mock_invoke_stream
        
        with pytest.raises(HTTPException) as exc_info:
            async for chunk in chat_service.stream_openai_text("conversation_1", "Hello"):
                pass
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @pytest.mark.asyncio
    async def test_stream_openai_text_no_response(self, chat_service):
        """Test streaming when no response is received."""
        # Setup agent to return empty response
        async def mock_invoke_stream(*args, **kwargs):
            return
            yield  # This makes it an async generator but yields nothing
        
        chat_service.agent.invoke_stream = mock_invoke_stream
        
        chunks = []
        async for chunk in chat_service.stream_openai_text("conversation_1", "Hello"):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert "I cannot answer this question with the current data" in chunks[0]
    
    @pytest.mark.asyncio
    @patch('services.chat_service.uuid.uuid4')
    @patch('services.chat_service.time.time')
    @patch('services.chat_service.format_stream_response')
    async def test_stream_chat_request_success(self, mock_format_stream, mock_time, mock_uuid, chat_service):
        """Test successful stream chat request."""
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
    async def test_stream_chat_request_agent_exception_rate_limit(self, chat_service):
        """Test stream_chat_request with AgentException for rate limiting."""
        error_message = "Rate limit is exceeded. Try again in 60 seconds"
        
        async def mock_stream_openai_text_rate_limit_error(conversation_id, query):
            raise RealAgentException(error_message)
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
        assert "Rate limit is exceeded. Try again in 60 seconds." == error_data["error"]

    @pytest.mark.asyncio
    async def test_stream_chat_request_agent_exception_generic(self, chat_service):
        """Test stream_chat_request with a generic AgentException."""
        error_message = "Some other agent error"

        async def mock_stream_openai_text_generic_error(conversation_id, query):
            raise RealAgentException(error_message)
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
    async def test_stream_chat_request_generic_exception(self, chat_service):
        """Test stream_chat_request with a generic Exception."""
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
    
    @pytest.mark.asyncio
    @patch('services.chat_service.uuid.uuid4')
    @patch('services.chat_service.time.time')
    async def test_complete_chat_request_success(self, mock_time, mock_uuid, chat_service):
        """Test successful complete chat request."""
        mock_uuid.return_value = "test-uuid"
        mock_time.return_value = 1234567890
        
        # Mock process_rag_response to return valid chart data
        def mock_process_rag_response(rag_response, query):
            return {"type": "bar", "data": {"labels": ["A"], "datasets": [{"data": [1]}]}}
        
        chat_service.process_rag_response = mock_process_rag_response
        
        result = await chat_service.complete_chat_request("Query", last_rag_response="RAG response")
        
        assert result["id"] == "test-uuid"
        assert result["model"] == "azure-openai"
        assert result["created"] == 1234567890
        assert "object" in result
        assert result["object"]["type"] == "bar"
    
    @pytest.mark.asyncio
    async def test_complete_chat_request_no_rag_response(self, chat_service):
        """Test complete chat request without RAG response."""
        result = await chat_service.complete_chat_request("Query", last_rag_response=None)
        
        assert "error" in result
        assert result["error"] == "A previous RAG response is required to generate a chart."
    
    @pytest.mark.asyncio
    async def test_complete_chat_request_chart_error(self, chat_service):
        """Test complete chat request when chart generation fails."""
        # Mock process_rag_response to return error
        def mock_process_rag_response(rag_response, query):
            return {"error": "Chart generation failed"}
        
        chat_service.process_rag_response = mock_process_rag_response
        
        result = await chat_service.complete_chat_request("Query", last_rag_response="RAG response")
        
        assert "error" in result
        assert "Chart could not be generated from this data" in result["error"]
        assert "error_desc" in result
    
    @pytest.mark.asyncio
    async def test_complete_chat_request_empty_chart_data(self, chat_service):
        """Test complete chat request when chart data is empty."""
        # Mock process_rag_response to return empty data
        def mock_process_rag_response(rag_response, query):
            return None
        
        chat_service.process_rag_response = mock_process_rag_response
        
        result = await chat_service.complete_chat_request("Query", last_rag_response="RAG response")
        
        assert "error" in result
        assert "Chart could not be generated from this data" in result["error"]
