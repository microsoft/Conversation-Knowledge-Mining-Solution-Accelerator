from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.modules.rag.service import rag_service
from backend.modules.rag.models import QARequest, QAResponse, ConversationRequest
from backend.modules.security.auth import get_current_user
from backend.modules.security.models import User

router = APIRouter()


class SaveChatRequest(BaseModel):
    session_id: str
    messages: list[dict]
    user_id: str = "default"
    title: Optional[str] = None


@router.post("/chat/save")
async def save_chat(request: SaveChatRequest, user: User = Depends(get_current_user)):
    """Save chat messages."""
    try:
        from backend.storage.db_service import db_service
        sessions = db_service.list_sessions(request.user_id)
        session_exists = any(s["id"] == request.session_id for s in sessions)
        if not session_exists:
            db_service.create_session(
                user_id=request.user_id,
                title=request.title or "Chat session",
            )
        success = db_service.save_messages_bulk(request.session_id, request.messages)
        if success:
            db_service.update_session(
                request.session_id, request.user_id,
                title=request.title,
                message_count=len(request.messages),
            )
        return {"saved": success}
    except Exception as e:
        return {"saved": False, "error": str(e)}


@router.get("/chat/load/{session_id}")
async def load_chat(session_id: str, user: User = Depends(get_current_user)):
    """Load chat messages."""
    try:
        from backend.storage.db_service import db_service
        messages = db_service.get_messages(session_id)
        return {"messages": messages}
    except Exception:
        return {"messages": []}


@router.get("/chat/sessions")
async def list_chat_sessions(user_id: str = "default", user: User = Depends(get_current_user)):
    """List all chat sessions for a user."""
    try:
        from backend.storage.db_service import db_service
        sessions = db_service.list_sessions(user_id)
        return {"sessions": sessions}
    except Exception:
        return {"sessions": []}


@router.delete("/chat/session/{session_id}")
async def delete_chat_session(session_id: str, user_id: str = "default", user: User = Depends(get_current_user)):
    """Delete a chat session and all its messages."""
    try:
        from backend.storage.db_service import db_service
        success = db_service.delete_session(session_id, user_id)
        return {"deleted": success}
    except Exception:
        return {"deleted": False}


@router.post("/ask", response_model=QAResponse)
async def ask_question(request: QARequest, user: User = Depends(get_current_user)):
    """Ask a question against the knowledge base or an external index."""
    try:
        doc_ids = request.document_ids if request.chat_scope == "documents" else None
        return rag_service.answer_question(
            question=request.question,
            top_k=request.top_k,
            filters=request.filters,
            include_sources=request.include_sources,
            document_ids=doc_ids,
            external_index_id=request.external_index_id if request.chat_scope == "external" else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {e}")


@router.post("/conversation", response_model=QAResponse)
async def conversation(request: ConversationRequest, user: User = Depends(get_current_user)):
    """Multi-turn conversation with RAG retrieval."""
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    try:
        doc_ids = request.document_ids if request.chat_scope == "documents" else None
        return rag_service.answer_conversation(
            messages=messages, top_k=request.top_k, filters=request.filters, document_ids=doc_ids
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversation failed: {e}")
