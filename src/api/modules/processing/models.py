from pydantic import BaseModel
from typing import Optional


class SummarizeRequest(BaseModel):
    text: str
    max_length: int = 200
    style: str = "concise"  # concise | detailed | bullet_points


class SummarizeResponse(BaseModel):
    original_length: int
    summary: str
    style: str


class EntityExtractionRequest(BaseModel):
    text: str
    entity_types: Optional[list[str]] = None  # None = extract all


class Entity(BaseModel):
    text: str
    type: str
    confidence: Optional[float] = None


class EntityExtractionResponse(BaseModel):
    entities: list[Entity]
    entity_count: int


class BatchProcessRequest(BaseModel):
    doc_ids: Optional[list[str]] = None  # None = process all ingested docs
    operations: list[str]  # ["summarize", "extract_entities"]


class BatchProcessResult(BaseModel):
    processed: int
    results: dict[str, dict]  # doc_id -> {summary, entities, ...}
    errors: list[str]
