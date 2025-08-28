import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status

# ---- Import service under test ----
from services.history_service import HistoryService


@pytest.fixture
def mock_config_instance():
    config = MagicMock()
    config.use_chat_history_enabled = True
    config.azure_cosmosdb_database = "test-db"
    config.azure_cosmosdb_account = "test-account"
    config.azure_cosmosdb_conversations_container = "test-container"
    config.azure_cosmosdb_enable_feedback = True
    config.azure_openai_endpoint = "https://test-openai.openai.azure.com/"
    config.azure_openai_api_version = "2024-02-15-preview"
    config.azure_openai_deployment_model = "gpt-4o-mini"
    config.azure_openai_resource = "test-resource"
    return config


@pytest.fixture
def history_service(mock_config_instance):
    # Create a patch for Config in the specific module where HistoryService looks it up
    with patch("services.history_service.Config", return_value=mock_config_instance):
        # Create patches for other dependencies used by HistoryService
        with patch("services.history_service.CosmosConversationClient"):
            with patch("services.history_service.AsyncAzureOpenAI"):
                with patch("helpers.azure_openai_helper.get_bearer_token_provider"):
                    with patch("services.history_service.complete_chat_request"):
                        service = HistoryService()
                        return service


@pytest.fixture
def mock_cosmos_client():
    client = AsyncMock()
    client.cosmosdb_client = AsyncMock()
    return client


@pytest.fixture
def mock_openai_client():
    client = AsyncMock()
    chat_completions = AsyncMock()
    client.chat.completions.create = AsyncMock()
    client.chat.completions = chat_completions
    return client


class TestHistoryService:
    def test_init(self, history_service, mock_config_instance):
        """Test service initialization with config values"""
        assert history_service.use_chat_history_enabled == mock_config_instance.use_chat_history_enabled
        assert history_service.azure_cosmosdb_database == mock_config_instance.azure_cosmosdb_database
        assert history_service.azure_cosmosdb_account == mock_config_instance.azure_cosmosdb_account
        assert history_service.azure_openai_endpoint == mock_config_instance.azure_openai_endpoint
        assert history_service.chat_history_enabled

    def test_init_cosmosdb_client_enabled(self, history_service):
        """Test CosmosDB client initialization when enabled"""
        with patch("services.history_service.CosmosConversationClient", return_value="cosmos_client"):
            client = history_service.init_cosmosdb_client()
            assert client == "cosmos_client"

    def test_init_cosmosdb_client_disabled(self, history_service):
        """Test CosmosDB client initialization when disabled"""
        history_service.chat_history_enabled = False
        client = history_service.init_cosmosdb_client()
        assert client is None

    def test_init_cosmosdb_client_exception(self, history_service):
        """Test CosmosDB client initialization with exception"""
        with patch("services.history_service.CosmosConversationClient", side_effect=Exception("Test error")):
            with pytest.raises(Exception):
                history_service.init_cosmosdb_client()

    def test_init_openai_client_with_endpoint(self, history_service):
        """Test OpenAI client initialization with endpoint"""
        with patch("services.history_service.AsyncAzureOpenAI", return_value="openai_client"):
            client = history_service.init_openai_client()
            assert client == "openai_client"

    def test_init_openai_client_with_resource(self, history_service):
        """Test OpenAI client initialization with resource"""
        history_service.azure_openai_endpoint = None
        with patch("services.history_service.AsyncAzureOpenAI", return_value="openai_client"):
            client = history_service.init_openai_client()
            assert client == "openai_client"

    def test_init_openai_client_no_endpoint_no_resource(self, history_service):
        """Test OpenAI client initialization with no endpoint or resource"""
        history_service.azure_openai_endpoint = None
        history_service.azure_openai_resource = None
        with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_RESOURCE is required"):
            history_service.init_openai_client()

    def test_init_openai_client_no_deployment_name(self, history_service):
        """Test OpenAI client initialization with no deployment name"""
        history_service.azure_openai_deployment_name = None
        with pytest.raises(ValueError, match="AZURE_OPENAI_MODEL is required"):
            history_service.init_openai_client()

    def test_init_openai_client_no_api_key(self, history_service):
        """Test OpenAI client initialization with no API key"""
        with patch("helpers.azure_openai_helper.get_bearer_token_provider", return_value="token_provider"):
            with patch("services.history_service.AsyncAzureOpenAI", return_value="openai_client"):
                client = history_service.init_openai_client()
                assert client == "openai_client"

    @pytest.mark.asyncio
    async def test_generate_title(self, history_service):
        """Test generate title functionality"""
        conversation_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated Title"
        
        with patch.object(history_service, "init_openai_client") as mock_init_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_init_client.return_value = mock_client
            
            result = await history_service.generate_title(conversation_messages)
            assert result == "Generated Title"
            
            # Test title generation with exception
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Test error"))
            result = await history_service.generate_title([{"role": "user", "content": "Fallback content"}])
            assert result == "Fallback content"

    @pytest.mark.asyncio
    async def test_add_conversation_new(self, history_service):
        """Test adding a new conversation"""
        user_id = "test-user-id"
        request_json = {
            "conversation_id": None,
            "messages": [{"role": "user", "content": "Hello"}]
        }
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.create_conversation = AsyncMock(
            return_value={"id": "new-conv-id", "title": "Test Title", "createdAt": "2023-01-01T00:00:00Z"}
        )
        mock_cosmos_client.create_message = AsyncMock(return_value="success")
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            with patch.object(history_service, "generate_title", AsyncMock(return_value="Test Title")):
                with patch("services.history_service.complete_chat_request", AsyncMock(return_value={"response": "test"})):
                    result = await history_service.add_conversation(user_id, request_json)
                    assert result == {"response": "test"}
                    
                    # Verify calls
                    mock_cosmos_client.create_conversation.assert_awaited_once()
                    mock_cosmos_client.create_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_conversation_existing(self, history_service):
        """Test adding to an existing conversation"""
        user_id = "test-user-id"
        request_json = {
            "conversation_id": "existing-id",
            "messages": [{"role": "user", "content": "Hello"}]
        }
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.create_message = AsyncMock(return_value="success")
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            with patch("services.history_service.complete_chat_request", AsyncMock(return_value={"response": "test"})):
                result = await history_service.add_conversation(user_id, request_json)
                assert result == {"response": "test"}
                
                # Verify calls
                mock_cosmos_client.create_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_conversation_cosmos_not_configured(self, history_service):
        """Test adding conversation when cosmos is not configured"""
        user_id = "test-user-id"
        request_json = {
            "conversation_id": "existing-id",
            "messages": [{"role": "user", "content": "Hello"}]
        }
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=None):
            with pytest.raises(ValueError, match="CosmosDB is not configured or unavailable"):
                await history_service.add_conversation(user_id, request_json)

    @pytest.mark.asyncio
    async def test_add_conversation_no_user_message(self, history_service):
        """Test adding conversation with no user message"""
        user_id = "test-user-id"
        request_json = {
            "conversation_id": "existing-id",
            "messages": [{"role": "assistant", "content": "Hello"}]
        }
        
        mock_cosmos_client = AsyncMock()
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            with pytest.raises(ValueError, match="No user message found"):
                await history_service.add_conversation(user_id, request_json)

    @pytest.mark.asyncio
    async def test_add_conversation_conversation_not_found(self, history_service):
        """Test adding to a non-existent conversation"""
        user_id = "test-user-id"
        request_json = {
            "conversation_id": "non-existent-id",
            "messages": [{"role": "user", "content": "Hello"}]
        }
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.create_message = AsyncMock(return_value="Conversation not found")
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            with pytest.raises(ValueError, match="Conversation not found"):
                await history_service.add_conversation(user_id, request_json)

    @pytest.mark.asyncio
    async def test_update_conversation(self, history_service):
        """Test updating an existing conversation"""
        user_id = "test-user-id"
        request_json = {
            "conversation_id": "existing-id",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there", "id": "msg-id"}
            ]
        }
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(
            return_value={"id": "existing-id", "title": "Test Title", "updatedAt": "2023-01-01T00:00:00Z"}
        )
        mock_cosmos_client.create_message = AsyncMock(return_value="success")
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.update_conversation(user_id, request_json)
            assert result == {
                "id": "existing-id", 
                "title": "Test Title", 
                "updatedAt": "2023-01-01T00:00:00Z"
            }
            
            # Verify calls
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.create_message.assert_awaited()
            mock_cosmos_client.cosmosdb_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_conversation_with_tool(self, history_service):
        """Test updating conversation with tool message"""
        user_id = "test-user-id"
        request_json = {
            "conversation_id": "existing-id",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "tool", "content": "Tool content"},
                {"role": "assistant", "content": "Hi there", "id": "msg-id"}
            ]
        }
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(
            return_value={"id": "existing-id", "title": "Test Title", "updatedAt": "2023-01-01T00:00:00Z"}
        )
        mock_cosmos_client.create_message = AsyncMock(return_value="success")
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.update_conversation(user_id, request_json)
            assert result == {
                "id": "existing-id", 
                "title": "Test Title", 
                "updatedAt": "2023-01-01T00:00:00Z"
            }
            
            # Verify calls
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.create_message.assert_awaited()
            assert mock_cosmos_client.create_message.await_count > 1
            mock_cosmos_client.cosmosdb_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_conversation_not_found(self, history_service):
        """Test updating a non-existent conversation"""
        user_id = "test-user-id"
        request_json = {
            "conversation_id": "non-existent-id",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there", "id": "msg-id"}
            ]
        }
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(return_value=None)
        mock_generate_title = AsyncMock(return_value="Generated Title")
        mock_cosmos_client.create_conversation = AsyncMock(
            return_value={"id": "new-id", "title": "Generated Title"}
        )
        mock_cosmos_client.create_message = AsyncMock(return_value="success")
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            with patch.object(history_service, "generate_title", mock_generate_title):
                result = await history_service.update_conversation(user_id, request_json)

                assert result == {"id": "new-id", "title": "Generated Title", "updatedAt": None}

                # Verify calls
                mock_cosmos_client.get_conversation.assert_awaited_once()
                mock_generate_title.assert_awaited_once()
                mock_cosmos_client.create_conversation.assert_awaited_once()
                mock_cosmos_client.create_message.assert_awaited()
                mock_cosmos_client.cosmosdb_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_conversation_no_conversation_id(self, history_service):
        """Test updating conversation with no conversation ID"""
        user_id = "test-user-id"
        request_json = {
            "conversation_id": None,
            "messages": [{"role": "user", "content": "Hello"}]
        }
        
        with pytest.raises(ValueError, match="No conversation_id found"):
            await history_service.update_conversation(user_id, request_json)

    @pytest.mark.asyncio
    async def test_update_conversation_conversation_not_found_error(self, history_service):
        """Test error when conversation not found during message creation"""
        user_id = "test-user-id"
        request_json = {
            "conversation_id": "existing-id",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there", "id": "msg-id"}
            ]
        }

        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(
            return_value={"id": "existing-id", "title": "Test Title", "updatedAt": "2023-01-01T00:00:00Z"}
        )
        mock_cosmos_client.create_message = AsyncMock(return_value="Conversation not found")

        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            with pytest.raises(HTTPException) as exc_info:
                await history_service.update_conversation(user_id, request_json)

            # Verify exception details
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert exc_info.value.detail == "Conversation not found"
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.create_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_conversation_no_user_message(self, history_service):
        """Test error when no user message is found in the request"""
        user_id = "test-user-id"
        request_json = {
            "conversation_id": "existing-id",
            "messages": [
                {"role": "assistant", "content": "Hi there", "id": "msg-id"}
            ]
        }

        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(
            return_value={"id": "existing-id", "title": "Test Title", "updatedAt": "2023-01-01T00:00:00Z"}
        )

        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            with pytest.raises(HTTPException) as exc_info:
                await history_service.update_conversation(user_id, request_json)

            # Verify exception details
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert exc_info.value.detail == "User message not found"
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.create_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_conversation_no_assistant_message(self, history_service):
        """Test error when no assistant message is found in the request"""
        user_id = "test-user-id"
        request_json = {
            "conversation_id": "existing-id",
            "messages": [
                {"role": "user", "content": "Hello"}
            ]
        }

        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(
            return_value={"id": "existing-id", "title": "Test Title", "updatedAt": "2023-01-01T00:00:00Z"}
        )
        mock_cosmos_client.create_message = AsyncMock(return_value="success")

        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            with pytest.raises(HTTPException) as exc_info:
                await history_service.update_conversation(user_id, request_json)

            # Verify exception details
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert exc_info.value.detail == "No assistant message found"
            mock_cosmos_client.get_conversation.assert_awaited_once()
            # Verify that create_message was called for the user message but not beyond that
            mock_cosmos_client.create_message.assert_awaited_once()
            mock_cosmos_client.cosmosdb_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rename_conversation(self, history_service):
        """Test renaming a conversation"""
        user_id = "test-user-id"
        conversation_id = "conv-id"
        new_title = "New Title"
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(
            return_value={"id": conversation_id, "title": "Old Title"}
        )
        mock_cosmos_client.upsert_conversation = AsyncMock(
            return_value={"id": conversation_id, "title": new_title}
        )
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.rename_conversation(user_id, conversation_id, new_title)
            assert result == {"id": conversation_id, "title": new_title}
            
            # Verify calls
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.upsert_conversation.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rename_conversation_not_found(self, history_service):
        """Test renaming a non-existent conversation"""
        user_id = "test-user-id"
        conversation_id = "non-existent-id"
        new_title = "New Title"
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(return_value=None)
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            with pytest.raises(HTTPException) as exc_info:
                await history_service.rename_conversation(user_id, conversation_id, new_title)
            
            assert exc_info.value.status_code == 404
            mock_cosmos_client.get_conversation.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rename_conversation_null_id(self, history_service):
        """Test renaming a conversation with null/None conversation ID"""
        user_id = "test-user-id"
        conversation_id = None
        new_title = "New Title"

        with pytest.raises(ValueError, match="No conversation_id found"):
            await history_service.rename_conversation(user_id, conversation_id, new_title)

    @pytest.mark.asyncio
    async def test_update_message_feedback(self, history_service):
        """Test updating message feedback"""
        user_id = "test-user-id"
        message_id = "message-id"
        message_feedback = "thumbs_up"
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.update_message_feedback = AsyncMock(
            return_value={"id": message_id, "feedback": message_feedback}
        )
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.update_message_feedback(user_id, message_id, message_feedback)
            assert result == {"id": message_id, "feedback": message_feedback}
            
            # Verify calls
            mock_cosmos_client.update_message_feedback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_message_feedback_not_found(self, history_service):
        """Test updating message feedback when message not found or access denied"""
        user_id = "test-user-id"
        message_id = "nonexistent-message-id"
        message_feedback = "thumbs_up"
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.update_message_feedback = AsyncMock(return_value=None)
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.update_message_feedback(user_id, message_id, message_feedback)
            assert result is None
            
            # Verify calls
            mock_cosmos_client.update_message_feedback.assert_awaited_once_with(user_id, message_id, message_feedback)

    @pytest.mark.asyncio
    async def test_delete_conversation(self, history_service):
        """Test deleting a conversation"""
        user_id = "test-user-id"
        conversation_id = "conv-id"
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(
            return_value={"id": conversation_id, "userId": user_id}
        )
        mock_cosmos_client.delete_messages = AsyncMock()
        mock_cosmos_client.delete_conversation = AsyncMock()
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.delete_conversation(user_id, conversation_id)
            assert result is True
            
            # Verify calls
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.delete_messages.assert_awaited_once()
            mock_cosmos_client.delete_conversation.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, history_service):
        """Test deleting a conversation that doesn't exist"""
        user_id = "test-user-id"
        conversation_id = "nonexistent-conv-id"

        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(return_value=None)

        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.delete_conversation(user_id, conversation_id)

            # Should return False when conversation not found
            assert result is False

            # Verify calls
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.delete_messages.assert_not_awaited()
            mock_cosmos_client.delete_conversation.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_conversation_unauthorized(self, history_service):
        """Test deleting a conversation where user is not authorized"""
        user_id = "test-user-id"
        different_user_id = "different-user-id"
        conversation_id = "conv-id"

        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(
            return_value={"id": conversation_id, "userId": different_user_id}
        )

        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.delete_conversation(user_id, conversation_id)

            # Should return False when user doesn't have permission
            assert result is False

            # Verify calls
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.delete_messages.assert_not_awaited()
            mock_cosmos_client.delete_conversation.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_conversations(self, history_service):
        """Test getting conversations"""
        user_id = "test-user-id"
        offset = 0
        limit = 10
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversations = AsyncMock(
            return_value=[
                {"id": "conv1", "title": "Conversation 1"},
                {"id": "conv2", "title": "Conversation 2"}
            ]
        )
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.get_conversations(user_id, offset, limit)
            assert len(result) == 2
            assert result[0]["id"] == "conv1"
            assert result[1]["title"] == "Conversation 2"
            
            # Verify calls
            mock_cosmos_client.get_conversations.assert_awaited_once_with(user_id, offset=offset, limit=limit)

    @pytest.mark.asyncio
    async def test_get_messages(self, history_service):
        """Test getting messages for a conversation"""
        user_id = "test-user-id"
        conversation_id = "conv-id"
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(
            return_value={"id": conversation_id, "userId": user_id}
        )
        mock_cosmos_client.get_messages = AsyncMock(
            return_value=[
                {"id": "msg1", "role": "user", "content": "Hello"},
                {"id": "msg2", "role": "assistant", "content": "Hi there"}
            ]
        )
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.get_messages(user_id, conversation_id)
            assert len(result) == 2
            assert result[0]["id"] == "msg1"
            assert result[1]["content"] == "Hi there"
            
            # Verify calls
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.get_messages.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_messages_conversation_not_found(self, history_service):
        """Test getting messages for a conversation that doesn't exist"""
        user_id = "test-user-id"
        conversation_id = "nonexistent-conv-id"

        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(return_value=None)

        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.get_messages(user_id, conversation_id)

            # Should return empty list when conversation not found
            assert result == []

            # Verify calls
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.get_messages.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_conversation_messages(self, history_service):
        """Test getting conversation with its messages"""
        user_id = "test-user-id"
        conversation_id = "conv-id"
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(
            return_value={"id": conversation_id, "userId": user_id}
        )
        mock_cosmos_client.get_messages = AsyncMock(
            return_value=[
                {"id": "msg1", "role": "user", "content": "Hello", "createdAt": "2023-01-01T00:00:00Z"},
                {"id": "msg2", "role": "assistant", "content": "Hi there", "createdAt": "2023-01-01T00:01:00Z", "feedback": "thumbs_up"}
            ]
        )
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.get_conversation_messages(user_id, conversation_id)
            assert len(result) == 2
            assert result[0]["id"] == "msg1"
            assert result[1]["feedback"] == "thumbs_up"
            
            # Verify calls
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.get_messages.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_conversation_messages_not_found(self, history_service):
        """Test getting conversation messages when conversation doesn't exist"""
        user_id = "test-user-id"
        conversation_id = "nonexistent-conv-id"

        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(return_value=None)

        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.get_conversation_messages(user_id, conversation_id)

            # Should return None when conversation not found
            assert result is None

            # Verify calls
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.get_messages.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_clear_messages(self, history_service):
        """Test clearing messages from a conversation"""
        user_id = "test-user-id"
        conversation_id = "conv-id"
        
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(
            return_value={"id": conversation_id, "user_id": user_id}
        )
        mock_cosmos_client.delete_messages = AsyncMock()
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.clear_messages(user_id, conversation_id)
            assert result is True
            
            # Verify calls
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.delete_messages.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clear_messages_conversation_not_found(self, history_service):
        """Test clearing messages when conversation doesn't exist"""
        user_id = "test-user-id"
        conversation_id = "nonexistent-conv-id"

        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(return_value=None)

        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.clear_messages(user_id, conversation_id)

            # Should return False when conversation not found
            assert result is False

            # Verify calls
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.delete_messages.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_clear_messages_unauthorized(self, history_service):
        """Test clearing messages when user doesn't have permission"""
        user_id = "test-user-id"
        different_user_id = "different-user-id"
        conversation_id = "conv-id"

        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.get_conversation = AsyncMock(
            return_value={"id": conversation_id, "user_id": different_user_id}
        )

        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            result = await history_service.clear_messages(user_id, conversation_id)

            # Should return False when user doesn't have permission
            assert result is False

            # Verify calls
            mock_cosmos_client.get_conversation.assert_awaited_once()
            mock_cosmos_client.delete_messages.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ensure_cosmos(self, history_service):
        """Test ensuring cosmos configuration"""
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.ensure = AsyncMock(return_value=(True, None))
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            success, error = await history_service.ensure_cosmos()
            assert success is True
            assert error is None
            
            # Verify calls
            mock_cosmos_client.ensure.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ensure_cosmos_exception(self, history_service):
        """Test exception handling in ensure_cosmos method"""
        test_error = Exception("Test database connection error")
        
        # Method 1: Mock the init_cosmosdb_client to throw an exception
        with patch.object(history_service, "init_cosmosdb_client", side_effect=test_error):
            success, error = await history_service.ensure_cosmos()
            assert success is False
            assert error == "Test database connection error"
        
        # Method 2: Mock a successful client init but failed ensure() call
        mock_cosmos_client = AsyncMock()
        mock_cosmos_client.ensure = AsyncMock(side_effect=test_error)
        
        with patch.object(history_service, "init_cosmosdb_client", return_value=mock_cosmos_client):
            success, error = await history_service.ensure_cosmos()
            assert success is False
            assert error == "Test database connection error"
            mock_cosmos_client.ensure.assert_awaited_once()