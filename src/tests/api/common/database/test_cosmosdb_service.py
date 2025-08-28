from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from azure.cosmos import exceptions
from common.database.cosmosdb_service import CosmosConversationClient


class AsyncIteratorWrapper:
    """Utility class to wrap async iteration over items."""
    def __init__(self, items):
        self._items = items

    def __aiter__(self):
        return self._async_gen()

    async def _async_gen(self):
        for item in self._items:
            yield item


@pytest.fixture
def mock_cosmos_clients():
    """Fixture to mock Cosmos DB container, database, and client."""
    mock_container = MagicMock()
    mock_database = MagicMock()
    mock_database.get_container_client.return_value = mock_container
    mock_cosmos = MagicMock()
    mock_cosmos.get_database_client.return_value = mock_database
    return mock_cosmos, mock_database, mock_container


@pytest.fixture
def cosmos_client(mock_cosmos_clients):
    """Fixture to create a CosmosConversationClient instance with mocked CosmosClient."""
    cosmos_mock, _, _ = mock_cosmos_clients
    with patch("common.database.cosmosdb_service.CosmosClient", return_value=cosmos_mock):
        return CosmosConversationClient(
            cosmosdb_endpoint="https://fake-cosmos.documents.azure.com",
            credential="fake-key",
            database_name="test-db",
            container_name="test-container"
        )


class TestCosmosDbService:

    @pytest.mark.asyncio
    async def test_ensure_success(self, cosmos_client, mock_cosmos_clients):
        """Test ensure() returns success if both DB and container are accessible."""
        _, db, container = mock_cosmos_clients
        db.read = AsyncMock(return_value=True)
        container.read = AsyncMock(return_value=True)
        result, msg = await cosmos_client.ensure()
        assert result is True and "successfully" in msg

    @pytest.mark.asyncio
    async def test_ensure_fail_when_client_is_none(self):
        """Test ensure() fails if cosmos client is not initialized."""
        client = CosmosConversationClient("url", "key", "db", "container")
        client.cosmosdb_client = None
        result, msg = await client.ensure()
        assert result is False and "not initialized" in msg

    @pytest.mark.asyncio
    async def test_ensure_database_read_fails(self, cosmos_client, mock_cosmos_clients):
        """Test ensure() fails when reading DB fails."""
        _, db, _ = mock_cosmos_clients
        db.read = AsyncMock(side_effect=Exception("Fail"))
        result, msg = await cosmos_client.ensure()
        assert result is False and "not found" in msg

    @pytest.mark.asyncio
    async def test_ensure_container_read_fails(self, cosmos_client, mock_cosmos_clients):
        """Test ensure() fails when reading container fails."""
        _, db, container = mock_cosmos_clients
        db.read = AsyncMock(return_value=True)
        container.read = AsyncMock(side_effect=Exception("Fail"))
        result, msg = await cosmos_client.ensure()
        assert result is False and "container" in msg

    def test_constructor_invalid_credential(self):
        """Test constructor raises ValueError on bad credentials."""
        with patch("common.database.cosmosdb_service.CosmosClient", side_effect=exceptions.CosmosHttpResponseError(status_code=401)):
            with pytest.raises(ValueError, match="Invalid credentials"):
                CosmosConversationClient("url", "bad", "db", "container")

    def test_constructor_invalid_database(self):
        """Test constructor raises ValueError for invalid DB name."""
        cosmos_mock = MagicMock()
        cosmos_mock.get_database_client.side_effect = exceptions.CosmosResourceNotFoundError()
        with patch("common.database.cosmosdb_service.CosmosClient", return_value=cosmos_mock):
            with pytest.raises(ValueError, match="Invalid CosmosDB database name"):
                CosmosConversationClient("url", "key", "invalid", "container")

    def test_constructor_invalid_container(self):
        """Test constructor raises ValueError for invalid container."""
        cosmos_mock = MagicMock()
        db_mock = MagicMock()
        db_mock.get_container_client.side_effect = exceptions.CosmosResourceNotFoundError()
        cosmos_mock.get_database_client.return_value = db_mock
        with patch("common.database.cosmosdb_service.CosmosClient", return_value=cosmos_mock):
            with pytest.raises(ValueError, match="Invalid CosmosDB container name"):
                CosmosConversationClient("url", "key", "db", "bad")

    @pytest.mark.asyncio
    async def test_create_conversation_success(self, cosmos_client, mock_cosmos_clients):
        """Test successful creation of conversation."""
        _, _, container = mock_cosmos_clients
        container.upsert_item = AsyncMock(return_value={"id": "c1"})
        result = await cosmos_client.create_conversation("user1", "c1", "title")
        assert result["id"] == "c1"

    @pytest.mark.asyncio
    async def test_create_conversation_failure(self, cosmos_client, mock_cosmos_clients):
        """Test failure to create conversation returns False."""
        _, _, container = mock_cosmos_clients
        container.upsert_item = AsyncMock(return_value=None)
        result = await cosmos_client.create_conversation("user1", "c2", "title")
        assert result is False

    @pytest.mark.asyncio
    async def test_upsert_conversation_success(self, cosmos_client, mock_cosmos_clients):
        """Test successful upsert of conversation."""
        _, _, container = mock_cosmos_clients
        container.upsert_item = AsyncMock(return_value={"id": "x"})
        result = await cosmos_client.upsert_conversation({"id": "x"})
        assert result["id"] == "x"

    @pytest.mark.asyncio
    async def test_upsert_conversation_failure(self, cosmos_client, mock_cosmos_clients):
        """Test upsert returns False when result is None."""
        _, _, container = mock_cosmos_clients
        container.upsert_item = AsyncMock(return_value=None)
        result = await cosmos_client.upsert_conversation({"id": "x"})
        assert result is False

    @pytest.mark.asyncio
    async def test_get_conversation_found(self, cosmos_client, mock_cosmos_clients):
        """Test get_conversation returns a result if found."""
        _, _, container = mock_cosmos_clients
        container.query_items.return_value = AsyncIteratorWrapper([{"id": "c1"}])
        result = await cosmos_client.get_conversation("user1", "c1")
        assert result["id"] == "c1"

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, cosmos_client, mock_cosmos_clients):
        """Test get_conversation returns None when not found."""
        _, _, container = mock_cosmos_clients
        container.query_items.return_value = AsyncIteratorWrapper([])
        result = await cosmos_client.get_conversation("user1", "none")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_conversations_with_limit(self, cosmos_client, mock_cosmos_clients):
        """Test get_conversations returns a list of messages."""
        _, _, container = mock_cosmos_clients
        container.query_items.return_value = AsyncIteratorWrapper([{"id": "1"}, {"id": "2"}])
        result = await cosmos_client.get_conversations("user1", limit=2, offset=0)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_create_message_with_feedback(self, cosmos_client, mock_cosmos_clients):
        """Test message creation with feedback enabled."""
        _, _, container = mock_cosmos_clients
        cosmos_client.enable_message_feedback = True
        container.upsert_item = AsyncMock(return_value={"id": "m1"})
        cosmos_client.get_conversation = AsyncMock(return_value={"id": "c1", "updatedAt": "old"})
        cosmos_client.upsert_conversation = AsyncMock()
        result = await cosmos_client.create_message("m1", "c1", "user1", {"role": "user", "text": "hi"})
        assert result["id"] == "m1"

    @pytest.mark.asyncio
    async def test_create_message_without_feedback(self, cosmos_client, mock_cosmos_clients):
        """Test message creation with feedback disabled."""
        _, _, container = mock_cosmos_clients
        cosmos_client.enable_message_feedback = False
        container.upsert_item = AsyncMock(return_value={"id": "m2"})
        cosmos_client.get_conversation = AsyncMock(return_value={"id": "c2", "updatedAt": "old"})
        cosmos_client.upsert_conversation = AsyncMock()
        result = await cosmos_client.create_message("m2", "c2", "user1", {"role": "assistant", "text": "hello"})
        assert result["id"] == "m2"

    @pytest.mark.asyncio
    async def test_create_message_conversation_not_found(self, cosmos_client, mock_cosmos_clients):
        """Test message creation fails when conversation not found."""
        _, _, container = mock_cosmos_clients
        cosmos_client.enable_message_feedback = True
        container.upsert_item = AsyncMock(return_value={"id": "m3"})
        cosmos_client.get_conversation = AsyncMock(return_value=None)
        result = await cosmos_client.create_message("m3", "notfound", "user1", {"role": "user", "text": "nope"})
        assert result == "Conversation not found"

    @pytest.mark.asyncio
    async def test_update_message_feedback_success(self, cosmos_client, mock_cosmos_clients):
        """Test updating message feedback successfully."""
        _, _, container = mock_cosmos_clients
        container.read_item = AsyncMock(return_value={"id": "m1"})
        container.upsert_item = AsyncMock(return_value={"id": "m1", "feedback": "Good"})
        result = await cosmos_client.update_message_feedback("user1", "m1", "Good")
        assert result["feedback"] == "Good"

    @pytest.mark.asyncio
    async def test_update_message_feedback_not_found(self, cosmos_client, mock_cosmos_clients):
        """Test updating feedback fails when message is missing."""
        _, _, container = mock_cosmos_clients
        container.read_item = AsyncMock(return_value=None)
        result = await cosmos_client.update_message_feedback("user1", "m2", "Bad")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_messages(self, cosmos_client, mock_cosmos_clients):
        """Test getting messages for a conversation."""
        _, _, container = mock_cosmos_clients
        container.query_items.return_value = AsyncIteratorWrapper([
            {"id": "m1"}, {"id": "m2"}
        ])
        result = await cosmos_client.get_messages("user1", "c1")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_delete_messages_with_messages(self, cosmos_client, mock_cosmos_clients):
        """Test deleting messages when messages exist."""
        _, _, container = mock_cosmos_clients
        cosmos_client.get_messages = AsyncMock(return_value=[
            {"id": "m1"}, {"id": "m2"}
        ])
        container.delete_item = AsyncMock(return_value=True)
        result = await cosmos_client.delete_messages("c1", "user1")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_delete_messages_no_messages(self, cosmos_client):
        """Test delete_messages returns None when there are no messages."""
        cosmos_client.get_messages = AsyncMock(return_value=[])
        result = await cosmos_client.delete_messages("c1", "user1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_conversation_found(self, cosmos_client, mock_cosmos_clients):
        """Test deleting an existing conversation."""
        _, _, container = mock_cosmos_clients
        container.read_item = AsyncMock(return_value={"id": "c1"})
        container.delete_item = AsyncMock(return_value=True)
        result = await cosmos_client.delete_conversation("user1", "c1")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, cosmos_client, mock_cosmos_clients):
        """Test deleting a non-existent conversation returns True (no-op)."""
        _, _, container = mock_cosmos_clients
        container.read_item = AsyncMock(return_value=None)
        result = await cosmos_client.delete_conversation("user1", "none")
        assert result is True
