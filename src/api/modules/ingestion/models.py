from pydantic import BaseModel
from typing import Any, Optional


class DocumentMetadata(BaseModel):
    product: Optional[str] = None
    category: Optional[str] = None
    timestamp: Optional[str] = None
    source_type: Optional[str] = None  # email, ticket, policy, faq, chat, audio, pdf, etc.
    source_file: Optional[str] = None
    language: Optional[str] = None


class Document(BaseModel):
    id: str
    type: str
    text: Any  # str or list[dict] for audio transcripts
    metadata: DocumentMetadata


class IngestionResult(BaseModel):
    total_loaded: int
    by_type: dict[str, int]
    sample_ids: list[str]
    quick_insights: Optional["QuickInsights"] = None


class QuickInsights(BaseModel):
    summary: str = ""
    highlights: list[str] = []
    detected: list[str] = []
    keywords: list[str] = []


class IngestionStats(BaseModel):
    total_documents: int
    by_type: dict[str, int]
    by_dimension: dict[str, dict[str, int]] = {}  # dimension_label -> {value: count}


class UploadedFile(BaseModel):
    id: str
    filename: str
    doc_count: int
    summary: str = ""
    keywords: list[str] = []
    filter_values: dict[str, list[str]] = {}  # dimension_id -> [values]
    doc_ids: list[str] = []  # IDs of documents belonging to this file
    uploaded_at: str = ""


class FilterValue(BaseModel):
    value: str
    label: str
    count: int = 0


class FilterDimension(BaseModel):
    id: str
    label: str
    type: str = "multi_select"
    values: list[FilterValue] = []


class FilterSchema(BaseModel):
    domain: str = ""
    dimensions: list[FilterDimension] = []
