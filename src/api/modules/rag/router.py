from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import asyncio
import logging

from src.api.modules.rag.service import rag_service
from src.api.modules.rag.models import QARequest, QAResponse, ConversationRequest
from src.api.auth.auth_utils import get_authenticated_user_details

logger = logging.getLogger(__name__)
router = APIRouter()


class CitationContentRequest(BaseModel):
    url: str


@router.post("/fetch-azure-search-content")
async def fetch_azure_search_content(body: CitationContentRequest):
    """Fetch the content of a cited Azure AI Search document by its get_url.

    Accepts a JSON payload with a 'url' field and returns {content, title}
    (or {error}).
    """
    if not body.url:
        raise HTTPException(status_code=400, detail="URL is required")
    try:
        return await asyncio.to_thread(rag_service.fetch_citation_content, body.url)
    except Exception as e:
        logger.error(f"fetch-azure-search-content failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch citation content.")


class SaveChatRequest(BaseModel):
    session_id: str
    messages: list[dict]
    user_id: str = "default"
    title: Optional[str] = None


@router.post("/chat/save")
async def save_chat(body: SaveChatRequest, request: Request):
    """Save chat messages."""
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    try:
        from src.api.storage.db_service import db_service
        sessions = db_service.list_sessions(user_id)
        session_exists = any(s["id"] == body.session_id for s in sessions)

        resolved_title = None
        if not session_exists:
            resolved_title = body.title
            if body.messages:
                agent_title = await asyncio.to_thread(rag_service.generate_title, body.messages)
                if agent_title:
                    resolved_title = agent_title

        if not session_exists:
            db_service.create_session(
                session_id=body.session_id,
                user_id=user_id,
                title=resolved_title or "Chat session",
            )
        success = db_service.save_messages_bulk(body.session_id, body.messages)
        if success:
            db_service.update_session(
                body.session_id, user_id,
                title=resolved_title,
                message_count=len(body.messages),
            )
        return {"saved": success}
    except Exception as e:
        logger.error(f"Failed to save chat session '{body.session_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save chat session. Please try again.")


@router.get("/chat/load/{session_id}")
async def load_chat(session_id: str):
    """Load chat messages."""
    try:
        from src.api.storage.db_service import db_service
        messages = db_service.get_messages(session_id)
        return {"messages": messages}
    except Exception as e:
        logger.warning(f"Failed to load chat session '{session_id}': {e}")
        return {"messages": []}


@router.get("/chat/sessions")
async def list_chat_sessions(request: Request):
    """List all chat sessions for the current user."""
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    try:
        from src.api.storage.db_service import db_service
        sessions = db_service.list_sessions(user_id)
        return {"sessions": sessions}
    except Exception as e:
        logger.warning(f"Failed to list chat sessions for user '{user_id}': {e}")
        return {"sessions": []}


@router.delete("/chat/session/{session_id}")
async def delete_chat_session(session_id: str, request: Request):
    """Delete a chat session and all its messages."""
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    try:
        from src.api.storage.db_service import db_service
        success = db_service.delete_session(session_id, user_id)
        return {"deleted": success}
    except Exception as e:
        logger.warning(f"Failed to delete chat session '{session_id}': {e}")
        return {"deleted": False}


@router.post("/ask", response_model=QAResponse)
async def ask_question(request: QARequest):
    """Ask a question against the knowledge base or an external index."""
    try:
        doc_ids = request.document_ids if request.chat_scope == "documents" else None
        return await asyncio.to_thread(
            rag_service.answer_question,
            question=request.question,
            top_k=request.top_k,
            filters=request.filters,
            include_sources=request.include_sources,
            document_ids=doc_ids,
            external_index_id=request.external_index_id if request.chat_scope == "external" else None,
            conversation_id=request.conversation_id,
        )
    except Exception as e:
        logger.error(f"RAG query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while processing your question. Please try again.")


@router.post("/conversation", response_model=QAResponse)
async def conversation(request: ConversationRequest):
    """Multi-turn conversation with RAG retrieval."""
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    try:
        doc_ids = request.document_ids if request.chat_scope == "documents" else None
        return await asyncio.to_thread(
            rag_service.answer_conversation,
            messages=messages, top_k=request.top_k, filters=request.filters, document_ids=doc_ids,
            conversation_id=request.conversation_id,
        )
    except Exception as e:
        logger.error(f"Conversation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred during the conversation. Please try again.")
