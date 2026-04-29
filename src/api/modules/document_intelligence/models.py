from pydantic import BaseModel
from typing import Any, Optional


class ExtractedDocument(BaseModel):
    filename: str
    content_type: str
    markdown: str
    fields: Optional[dict[str, Any]] = None
    page_count: int = 1
    analyzer: str = "km-document"

    # AI-enriched fields (populated after GPT-4o analysis of CU output)
    summary: str = ""
    entities: list[dict[str, str]] = []  # [{name, type, context}]
    key_phrases: list[str] = []
    topics: list[str] = []
    metadata_extracted: dict[str, str] = {}  # key-value pairs extracted from content
