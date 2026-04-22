from pydantic import BaseModel
from typing import Any, Optional


class KnowledgeObject(BaseModel):
    """Unified data model that all capabilities read/write."""
    id: str
    type: str
    content: str
    chunks: list[str] = []
    metadata: dict[str, Any] = {}
    entities: list[dict[str, Any]] = []
    embeddings: list[list[float]] = []
    summary: Optional[str] = None
    fields: Optional[dict[str, Any]] = None
    source_file: Optional[str] = None
