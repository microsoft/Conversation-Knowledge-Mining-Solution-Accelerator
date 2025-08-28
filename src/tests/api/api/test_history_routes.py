import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from httpx import AsyncClient,ASGITransport
from api.history_routes import router
import json

app = FastAPI()
app.include_router(router)


@pytest.fixture
def headers():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def mock_user():
    return {"user_principal_id": "user123"}


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.add_conversation", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_add_conversation(mock_track, mock_add, mock_auth, client, headers):
    mock_auth.return_value = {"user_principal_id": "user123"}
    mock_add.return_value = {"result": "ok"}

    res = await client.post("/generate", json={"message": "hello"}, headers=headers)
    assert res.status_code == 200
    assert res.json() == {"result": "ok"}


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.update_conversation", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_update_conversation(mock_track, mock_update, mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    mock_update.return_value = {"title": "New Title", "updatedAt": "now", "id": "123"}

    res = await client.post("/update", json={"conversation_id": "123"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["title"] == "New Title"



@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.update_conversation", new_callable=AsyncMock)
async def test_update_conversation_missing_id(mock_update, mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    res = await client.post(
        "/update",
        json={},  
        headers={**headers, "Content-Type": "application/json"}
    )
    
    assert res.status_code == 500
    assert res.json()["error"] == "An internal error has occurred!"
    mock_update.assert_not_awaited()


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.update_message_feedback", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_update_message_feedback(mock_track, mock_update, mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    mock_update.return_value = True

    res = await client.post("/message_feedback", json={"message_id": "m1", "message_feedback": "positive"}, headers=headers)
    assert res.status_code == 200

@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
async def test_update_message_feedback_missing_message_id(mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    res = await client.post("/message_feedback", json={"message_feedback": "positive"}, headers=headers)
    assert res.status_code == 500
    assert res.json()["error"] == "An internal error has occurred!"


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
async def test_update_message_feedback_missing_feedback(mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    res = await client.post("/message_feedback", json={"message_id": "m1"}, headers=headers)
    assert res.status_code == 500
    assert res.json()["error"] == "An internal error has occurred!"


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.update_message_feedback", new_callable=AsyncMock)
async def test_update_message_feedback_not_found(mock_update, mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    mock_update.return_value = False
    res = await client.post(
        "/message_feedback", 
        json={"message_id": "m1", "message_feedback": "positive"}, 
        headers=headers
    )
    assert res.status_code == 500
    assert res.json()["error"] == "An internal error has occurred!"


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.delete_conversation", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_delete_conversation(mock_track, mock_delete, mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    mock_delete.return_value = True

    payload = {"conversation_id": "c1"}
    res = await client.request(
        "DELETE", "/delete",
        content=json.dumps(payload),
        headers={**headers, "Content-Type": "application/json"}
    )
    assert res.status_code == 200


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.delete_conversation", new_callable=AsyncMock)
async def test_delete_conversation_not_found(mock_delete, mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    mock_delete.return_value = False
    res = await client.request(
        "DELETE", "/delete",
        content=json.dumps({"conversation_id": "c1"}),
        headers={**headers, "Content-Type": "application/json"}
    )
    assert res.status_code == 500
    assert res.json()["error"] == "An internal error has occurred!"


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.get_conversations", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_list_conversations(mock_track, mock_get, mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    mock_get.return_value = [{"id": "c1"}]

    res = await client.get("/list?offset=0&limit=10", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.get_conversations", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_list_conversations_not_found(mock_track, mock_get, mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    mock_get.return_value = None

    res = await client.get("/list", headers=headers)
    assert res.status_code == 404
    assert "error" in res.json()



@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.get_conversation_messages", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_get_conversation_messages(mock_track, mock_get, mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    mock_get.return_value = [{"message": "hello"}]

    res = await client.post("/read", json={"conversation_id": "c1"}, headers=headers)
    assert res.status_code == 200
    assert "messages" in res.json()


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.get_conversation_messages", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_get_conversation_messages_not_found(mock_track, mock_get, mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    mock_get.return_value = None

    res = await client.post("/read", json={"conversation_id": "c1"}, headers=headers)
    assert res.status_code == 500
    assert res.json()["error"] == "An internal error has occurred!"



@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.rename_conversation", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_rename_conversation(mock_track, mock_rename, mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    mock_rename.return_value = {"title": "new name"}

    res = await client.post("/rename", json={"conversation_id": "c1", "title": "new name"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["title"] == "new name"


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
async def test_rename_conversation_missing_conversation_id(mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    res = await client.post("/rename", json={"title": "new name"}, headers=headers)
    assert res.status_code == 500
    assert res.json()["error"] == "An internal error has occurred!"


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
async def test_rename_conversation_missing_title(mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    res = await client.post("/rename", json={"conversation_id": "c1"}, headers=headers)
    assert res.status_code == 500
    assert res.json()["error"] == "An internal error has occurred!"



@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.get_conversations", new_callable=AsyncMock)
@patch("services.history_service.HistoryService.delete_conversation", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_delete_all_conversations(mock_track, mock_delete, mock_get, mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    mock_get.return_value = [{"id": "c1"}, {"id": "c2"}]
    mock_delete.return_value = True

    res = await client.request("DELETE", "/delete_all", headers=headers)
    assert res.status_code == 200


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details")
@patch("services.history_service.HistoryService.clear_messages", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_clear_messages(mock_track, mock_clear, mock_auth, client, headers, mock_user):
    mock_auth.return_value = mock_user
    mock_clear.return_value = True

    res = await client.post("/clear", json={"conversation_id": "c1"}, headers=headers)
    assert res.status_code == 200


@pytest.mark.asyncio
@patch("services.history_service.HistoryService.ensure_cosmos", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_ensure_cosmos(mock_track, mock_ensure, client):
    mock_ensure.return_value = (True, None)

    res = await client.get("/history/ensure")
    assert res.status_code == 200
    assert res.json()["message"] == "CosmosDB is configured and working"



@pytest.mark.asyncio
@patch("services.history_service.HistoryService.ensure_cosmos", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_ensure_cosmos_failure(mock_track, mock_ensure, client):
    mock_ensure.return_value = (False, "connection failed")
    res = await client.get("/history/ensure")
    assert res.status_code == 422
    assert "error" in res.json()


@pytest.mark.asyncio
@patch("services.history_service.HistoryService.ensure_cosmos", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_ensure_cosmos_invalid_credentials(mock_track, mock_ensure, client):
    mock_ensure.side_effect = Exception("Invalid credentials")
    res = await client.get("/history/ensure")
    assert res.status_code == 401
    assert res.json()["error"] == "Invalid credentials"


@pytest.mark.asyncio
@patch("services.history_service.HistoryService.ensure_cosmos", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_ensure_cosmos_invalid_config(mock_track, mock_ensure, client):
    mock_ensure.side_effect = Exception("Invalid CosmosDB database name")
    res = await client.get("/history/ensure")
    assert res.status_code == 422
    assert res.json()["error"] == "Invalid CosmosDB configuration"



@pytest.mark.asyncio
@patch("services.history_service.HistoryService.ensure_cosmos", new_callable=AsyncMock)
@patch("common.logging.event_utils.track_event_if_configured")
async def test_ensure_cosmos_unknown_error(mock_track, mock_ensure, client):
    mock_ensure.side_effect = Exception("Something went wrong")
    res = await client.get("/history/ensure")
    assert res.status_code == 500
    assert res.json()["error"] == "CosmosDB is not configured or not working"


@pytest.mark.asyncio
@patch("auth.auth_utils.get_authenticated_user_details", side_effect=Exception("auth error"))
async def test_add_conversation_exception(mock_auth, client, headers):
    res = await client.post("/generate", json={"message": "hi"}, headers=headers)
    assert res.status_code == 500