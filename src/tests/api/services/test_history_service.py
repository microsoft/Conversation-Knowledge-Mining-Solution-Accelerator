import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status

# ---- Import service under test ----
from services.history_service import HistoryService
from azure.ai.agents.models import MessageRole


@pytest.fixture
def mock_config_instance():
    config = MagicMock()
    config.use_chat_history_enabled = True
    config.azure_cosmosdb_database = "test-db"
    config.azure_cosmosdb_account = "test-account"
    config.azure_cosmosdb_conversations_container = "test-container"
    config.azure_cosmosdb_enable_feedback = True
    # Azure AI Foundry SDK configuration
    config.azure_openai_deployment_model = "gpt-4o-mini"  # Still needed for model parameter
    config.azure_client_id = "test-client-id"
    config.ai_project_endpoint = "https://test-aif.services.ai.azure.com/api/projects/test-project"
    config.ai_project_api_version = "2025-05-01"
    config.solution_name = "test-solution"
    return config


@pytest.fixture
def history_service(mock_config_instance):
    # Create a patch for Config in the specific module where HistoryService looks it up
    with patch("services.history_service.Config", return_value=mock_config_instance):
        # Create patches for other dependencies used by HistoryService
        with patch("services.history_service.CosmosConversationClient"):
            with patch("services.history_service.complete_chat_request"):
                service = HistoryService()
                return service


@pytest.fixture
def mock_cosmos_client():
    client = AsyncMock()
    client.cosmosdb_client = AsyncMock()
    return client


class TestHistoryService:
    def test_init(self, history_service, mock_config_instance):
        """Test service initialization with config values"""
        assert history_service.use_chat_history_enabled == mock_config_instance.use_chat_history_enabled
        assert history_service.azure_cosmosdb_database == mock_config_instance.azure_cosmosdb_database
        assert history_service.azure_cosmosdb_account == mock_config_instance.azure_cosmosdb_account
        assert history_service.azure_openai_deployment_name == mock_config_instance.azure_openai_deployment_model
        assert history_service.ai_project_endpoint == mock_config_instance.ai_project_endpoint
        assert history_service.ai_project_api_version == mock_config_instance.ai_project_api_version
        assert history_service.solution_name == mock_config_instance.solution_name
        assert history_service.azure_client_id == mock_config_instance.azure_client_id
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

    @pytest.mark.asyncio
    async def test_generate_title(self, history_service):
        """Test generate title functionality using Azure AI Foundry SDK"""
        conversation_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]

        # Mock the AIProjectClient and related objects
        mock_project_client = MagicMock()
        mock_agent = MagicMock()
        mock_agent.id = "test-agent-id"
        mock_thread = MagicMock()
        mock_thread.id = "test-thread-id"
        mock_run = MagicMock()
        mock_run.status = "completed"
        
        # Mock message with agent response
        mock_message = MagicMock()
        mock_message.role = MessageRole.AGENT
        mock_text_message = MagicMock()
        mock_text_message.text.value = "Billing Help Request"
        mock_message.text_messages = [mock_text_message]

        mock_project_client.agents.create_agent.return_value = mock_agent
        mock_project_client.agents.threads.create.return_value = mock_thread
        mock_project_client.agents.runs.create_and_process.return_value = mock_run
        mock_project_client.agents.messages.list.return_value = [mock_message]

        with patch("services.history_service.AIProjectClient", return_value=mock_project_client):
            with patch("services.history_service.get_azure_credential"):
                result = await history_service.generate_title(conversation_messages)
                assert result == "Billing Help Request"                # Verify the agent was created with correct parameters
                mock_project_client.agents.create_agent.assert_called_once()
                create_agent_call = mock_project_client.agents.create_agent.call_args
                assert create_agent_call[1]["model"] == "gpt-4o-mini"
                assert "TitleAgent-test-solution" in create_agent_call[1]["name"]
                
                # Verify cleanup was called
                mock_project_client.agents.threads.delete.assert_called_once_with(thread_id="test-thread-id")
                mock_project_client.agents.delete_agent.assert_called_once_with("test-agent-id")

    @pytest.mark.asyncio
    async def test_generate_title_failed_run(self, history_service):
        """Test generate title with failed AI run"""
        conversation_messages = [{"role": "user", "content": "Test message"}]
        
        # Mock failed run
        mock_project_client = MagicMock()
        mock_agent = MagicMock()
        mock_thread = MagicMock()
        mock_run = MagicMock()
        mock_run.status = "failed"
        mock_run.last_error = "Test error"
        
        mock_project_client.agents.create_agent.return_value = mock_agent
        mock_project_client.agents.threads.create.return_value = mock_thread
        mock_project_client.agents.runs.create_and_process.return_value = mock_run
        
        with patch("services.history_service.AIProjectClient", return_value=mock_project_client):
            with patch("services.history_service.get_azure_credential"):
                result = await history_service.generate_title(conversation_messages)
                assert result == "Test message"  # Should fall back to truncated user message

    @pytest.mark.asyncio
    async def test_generate_title_exception(self, history_service):
        """Test generate title with exception"""
        conversation_messages = [{"role": "user", "content": "Fallback content"}]
        
        with patch("services.history_service.AIProjectClient", side_effect=Exception("Test error")):
            result = await history_service.generate_title(conversation_messages)
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