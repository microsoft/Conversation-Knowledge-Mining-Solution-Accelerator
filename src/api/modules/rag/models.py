from pydantic import BaseModel
from typing import Literal, Optional


class QARequest(BaseModel):
    question: str
    top_k: int = 5
    filters: Optional[dict] = None
    include_sources: bool = True
    chat_scope: Literal["all", "documents", "external"] = "all"
    document_ids: Optional[list[str]] = None
    external_index_id: Optional[str] = None


class Source(BaseModel):
    doc_id: str
    score: float
    text: str
    metadata: dict


class QAResponse(BaseModel):
    question: str
    answer: str
    sources: list[Source] = []
    model: str


class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ConversationRequest(BaseModel):
    messages: list[ConversationMessage]
    top_k: int = 5
    filters: Optional[dict] = None
    chat_scope: Literal["all", "documents", "external"] = "all"
    document_ids: Optional[list[str]] = None
    external_index_id: Optional[str] = None
