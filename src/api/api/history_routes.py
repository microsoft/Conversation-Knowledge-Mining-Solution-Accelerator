import logging
import os
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from auth.auth_utils import get_authenticated_user_details
from services.history_service import HistoryService
from common.logging.event_utils import track_event_if_configured
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if the Application Insights Instrumentation Key is set in the environment variables
instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if instrumentation_key:
    # Configure Application Insights if the Instrumentation Key is found
    configure_azure_monitor(connection_string=instrumentation_key)
    logging.info("Application Insights configured with the provided Instrumentation Key")
else:
    # Log a warning if the Instrumentation Key is not found
    logging.warning("No Application Insights Instrumentation Key found. Skipping configuration")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Suppress INFO logs from 'azure.core.pipeline.policies.http_logging_policy'
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
logging.getLogger("azure.identity.aio._internal").setLevel(logging.WARNING)

# Suppress info logs from OpenTelemetry exporter
logging.getLogger("azure.monitor.opentelemetry.exporter.export._base").setLevel(
    logging.WARNING
)

# Single instance of HistoryService (if applicable)
history_service = HistoryService()


@router.post("/generate")
async def add_conversation(request: Request):
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()

        response = await history_service.add_conversation(user_id, request_json)
        track_event_if_configured("ConversationCreated", {
            "user_id": user_id,
            "request": request_json,
        })
        return response

    except Exception as e:
        logger.exception("Exception in /generate: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.post("/update")
async def update_conversation(request: Request):
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")

        if not conversation_id:
            raise HTTPException(status_code=400, detail="No conversation_id found")

        # Call HistoryService to update conversation
        update_response = await history_service.update_conversation(user_id, request_json)

        if not update_response:
            raise HTTPException(status_code=500, detail="Failed to update conversation")
        track_event_if_configured("ConversationUpdated", {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "title": update_response["title"]
        })

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "title": update_response["title"],
                    "date": update_response["updatedAt"],
                    "conversation_id": update_response["id"],
                },
            },
            status_code=200,
        )
    except Exception as e:
        logger.exception("Exception in /history/update: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.post("/message_feedback")
async def update_message_feedback(request: Request):
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()
        message_id = request_json.get("message_id")
        message_feedback = request_json.get("message_feedback")

        if not message_id:
            track_event_if_configured("MessageFeedbackValidationError", {
                "error": "message_id is missing",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="message_id is required")

        if not message_feedback:
            track_event_if_configured("MessageFeedbackValidationError", {
                "error": "message_feedback is missing",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="message_feedback is required")

        # Call HistoryService to update message feedback
        updated_message = await history_service.update_message_feedback(user_id, message_id, message_feedback)

        if updated_message:
            track_event_if_configured("MessageFeedbackUpdated", {
                "user_id": user_id,
                "message_id": message_id,
                "feedback": message_feedback
            })
            return JSONResponse(
                content={
                    "message": f"Successfully updated message with feedback {message_feedback}",
                    "message_id": message_id,
                },
                status_code=200,
            )
        else:
            track_event_if_configured("MessageFeedbackNotFound", {
                "user_id": user_id,
                "message_id": message_id
            })
            raise HTTPException(
                status_code=404,
                detail=f"Unable to update message {message_id}. It either does not exist or the user does not have access to it."
            )

    except Exception as e:
        logger.exception("Exception in /history/message_feedback: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.delete("/delete")
async def delete_conversation(request: Request):
    try:
        # Get the user ID from request headers
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]
        # Parse request body
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")
        if not conversation_id:
            track_event_if_configured("DeleteConversationValidationError", {
                "error": "conversation_id is missing",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="conversation_id is required")

        # Delete conversation using HistoryService
        deleted = await history_service.delete_conversation(user_id, conversation_id)
        if deleted:
            track_event_if_configured("ConversationDeleted", {
                "user_id": user_id,
                "conversation_id": conversation_id
            })
            return JSONResponse(
                content={
                    "message": "Successfully deleted conversation and messages",
                    "conversation_id": conversation_id},
                status_code=200,
            )
        else:
            track_event_if_configured("DeleteConversationNotFound", {
                "user_id": user_id,
                "conversation_id": conversation_id
            })
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found or user does not have permission.")
    except Exception as e:
        logger.exception("Exception in /history/delete: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.get("/list")
async def list_conversations(
    request: Request,
    offset: int = Query(0, alias="offset"),
    limit: int = Query(25, alias="limit")
):
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        logger.info(f"user_id: {user_id}, offset: {offset}, limit: {limit}")

        # Get conversations
        conversations = await history_service.get_conversations(user_id, offset=offset, limit=limit)

        if not isinstance(conversations, list):
            track_event_if_configured("ListConversationsNotFound", {
                "user_id": user_id,
                "offset": offset,
                "limit": limit
            })
            return JSONResponse(
                content={
                    "error": f"No conversations for {user_id} were found"},
                status_code=404)
        track_event_if_configured("ConversationsListed", {
            "user_id": user_id,
            "offset": offset,
            "limit": limit,
            "conversation_count": len(conversations)
        })
        return JSONResponse(content=conversations, status_code=200)

    except Exception as e:
        logger.exception("Exception in /history/list: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.post("/read")
async def get_conversation_messages(request: Request):
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")

        if not conversation_id:
            track_event_if_configured("ReadConversationValidationError", {
                "error": "conversation_id is required",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="conversation_id is required")

        # Get conversation details
        conversationMessages = await history_service.get_conversation_messages(user_id, conversation_id)
        if not conversationMessages:
            track_event_if_configured("ReadConversationNotFound", {
                "user_id": user_id,
                "conversation_id": conversation_id
            })
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} was not found. It either does not exist or the user does not have access to it."
            )
        track_event_if_configured("ConversationRead", {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "message_count": len(conversationMessages)
        })

        return JSONResponse(
            content={
                "conversation_id": conversation_id,
                "messages": conversationMessages},
            status_code=200)

    except Exception as e:
        logger.exception("Exception in /history/read: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.post("/rename")
async def rename_conversation(request: Request):
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")
        title = request_json.get("title")

        if not conversation_id:
            track_event_if_configured("RenameConversationValidationError", {
                "error": "conversation_id is required",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="conversation_id is required")
        if not title:
            track_event_if_configured("RenameConversationValidationError", {
                "error": "title is required",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="title is required")

        rename_conversation = await history_service.rename_conversation(user_id, conversation_id, title)

        track_event_if_configured("ConversationRenamed", {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "new_title": title
        })

        return JSONResponse(content=rename_conversation, status_code=200)

    except Exception as e:
        logger.exception("Exception in /history/rename: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.delete("/delete_all")
async def delete_all_conversations(request: Request):
    try:
        # Get the user ID from request headers
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Get all user conversations
        conversations = await history_service.get_conversations(user_id, offset=0, limit=None)
        if not conversations:
            track_event_if_configured("DeleteAllConversationsNotFound", {
                "user_id": user_id
            })
            raise HTTPException(status_code=404,
                                detail=f"No conversations for {user_id} were found")

        # Delete all conversations
        for conversation in conversations:
            await history_service.delete_conversation(user_id, conversation["id"])

        track_event_if_configured("AllConversationsDeleted", {
            "user_id": user_id,
            "deleted_count": len(conversations)
        })

        return JSONResponse(
            content={
                "message": f"Successfully deleted all conversations for user {user_id}"},
            status_code=200,
        )

    except Exception as e:
        logging.exception("Exception in /history/delete_all: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.post("/clear")
async def clear_messages(request: Request):
    try:
        # Get the user ID from request headers
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")

        if not conversation_id:
            track_event_if_configured("ClearMessagesValidationError", {
                "error": "conversation_id is required",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="conversation_id is required")

        # Delete conversation messages from CosmosDB
        success = await history_service.clear_messages(user_id, conversation_id)

        if not success:
            track_event_if_configured("ClearMessagesFailed", {
                "user_id": user_id,
                "conversation_id": conversation_id
            })
            raise HTTPException(
                status_code=404,
                detail="Failed to clear messages or conversation not found")
        track_event_if_configured("MessagesCleared", {
            "user_id": user_id,
            "conversation_id": conversation_id
        })

        return JSONResponse(
            content={
                "message": "Successfully cleared messages"},
            status_code=200)

    except Exception as e:
        logger.exception("Exception in /history/clear: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.get("/history/ensure")
async def ensure_cosmos():
    try:
        success, err = await history_service.ensure_cosmos()
        if not success:
            track_event_if_configured("CosmosDBEnsureFailed", {
                "error": err or "Unknown error occurred"
            })
            return JSONResponse(
                content={
                    "error": err or "Unknown error occurred"},
                status_code=422)
        track_event_if_configured("CosmosDBEnsureSuccess", {
            "status": "CosmosDB is configured and working"
        })

        return JSONResponse(
            content={
                "message": "CosmosDB is configured and working"},
            status_code=200)
    except Exception as e:
        logger.exception("Exception in /history/ensure: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        cosmos_exception = str(e)

        if "Invalid credentials" in cosmos_exception:
            return JSONResponse(content={"error": "Invalid credentials"}, status_code=401)
        elif "Invalid CosmosDB database name" in cosmos_exception or "Invalid CosmosDB container name" in cosmos_exception:
            return JSONResponse(content={"error": "Invalid CosmosDB configuration"}, status_code=422)
        else:
            return JSONResponse(
                content={
                    "error": "CosmosDB is not configured or not working"},
                status_code=500)
