from pydantic import BaseModel
from typing import Optional


class EmbeddingRequest(BaseModel):
    text: str


class EmbeddingResponse(BaseModel):
    text: str
    embedding: list[float]
    model: str
    dimensions: int


class IndexDocumentRequest(BaseModel):
    doc_id: Optional[str] = None


class IndexResult(BaseModel):
    indexed_count: int
    index_name: str
    errors: list[str] = []


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    filters: Optional[dict] = None


class SearchResult(BaseModel):
    doc_id: str
    score: float
    text: str
    metadata: dict
