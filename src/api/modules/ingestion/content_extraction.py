"""AI-powered content extraction for uploaded documents.

Two-phase extraction:
1. Per-document: summary + keywords
2. Dataset-wide: structured filter schema with dimensions, normalized values, counts
"""

import json
import logging
from typing import Optional

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from src.api.config import get_settings

logger = logging.getLogger(__name__)

# ── Phase 1: Per-document summary + keywords ──

DOC_EXTRACTION_PROMPT = """You extract structured metadata from documents.

For each document, produce:
- summary: 1-2 sentence summary of the content
- keywords: 3-6 specific, meaningful keywords (not generic)

Output strictly valid JSON:
{
  "documents": [
    {
      "id": "doc_id",
      "summary": "...",
      "keywords": ["...", "..."]
    }
  ]
}"""

# ── Phase 2: Structured filter schema ──

FILTER_SCHEMA_PROMPT = """You are an AI system responsible for generating a FILTER SCHEMA for a knowledge mining Explore page.

You will receive document summaries and keywords. Generate a STRUCTURED, DYNAMIC FILTER SCHEMA.

STEP 1 — Identify 4-8 Filter Dimensions
Automatically determine the most meaningful dimensions for this dataset.
Examples (DO NOT hardcode — infer from content):
- topics, entities, products, people, organizations
- intent, sentiment, document type, domain-specific concepts

STEP 2 — Normalize Values
For each dimension:
- Cluster similar meanings into a single label
- Remove duplicates and synonyms
- Ensure values are consistent and reusable

STEP 3 — Rank & Limit
For each dimension:
- Return only top 5-15 most relevant values
- Sort by frequency or relevance
- Include counts

STEP 4 — Map documents to filter values
For each document, specify which filter values apply.

Output ONLY this JSON:
{
  "domain": "string",
  "dimensions": [
    {
      "id": "string",
      "label": "string",
      "type": "multi_select",
      "values": [
        {
          "value": "string",
          "label": "string",
          "count": 0
        }
      ]
    }
  ],
  "document_filters": [
    {
      "id": "doc_id",
      "values": {
        "dimension_id": ["value1", "value2"]
      }
    }
  ]
}

RULES:
- Do NOT output raw keywords or free-text tags
- Keep schema minimal, clean, and UI-ready
- Adapt dynamically — do NOT assume any specific domain"""


class ContentExtractionService:
    """Extract structured metadata from documents using Azure OpenAI."""

    def __init__(self):
        self._client: Optional[AzureOpenAI] = None

    def _get_client(self) -> AzureOpenAI:
        if self._client is None:
            settings = get_settings()
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            self._client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version="2024-10-21",
            )
        return self._client

    def _call_llm(self, system: str, user: str, max_tokens: int = 4000) -> dict:
        settings = get_settings()
        client = self._get_client()
        response = client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON")
            return {}

    def extract_documents(self, documents: list[dict]) -> list[dict]:
        """Phase 1: Extract summary + keywords for each document."""
        doc_snippets = []
        for doc in documents:
            text = doc.get("text", "")
            if isinstance(text, list):
                text = "\n".join(
                    f"{seg.get('speaker', 'Unknown')}: {seg.get('text', '')}"
                    for seg in text
                )
            snippet = text[:600] + ("..." if len(text) > 600 else "")
            doc_snippets.append({"id": doc["id"], "type": doc.get("type", "unknown"), "text": snippet})

        user_prompt = (
            f"Extract metadata for these {len(doc_snippets)} documents:\n\n"
            + json.dumps(doc_snippets, indent=2)
        )

        result = self._call_llm(DOC_EXTRACTION_PROMPT, user_prompt)
        return result.get("documents", [])

    def extract_filter_schema(self, doc_extractions: list[dict]) -> dict:
        """Phase 2: Generate structured filter schema from document summaries/keywords."""
        # Build input from phase 1 results
        summaries = []
        for d in doc_extractions:
            summaries.append({
                "id": d.get("id", ""),
                "summary": d.get("summary", ""),
                "keywords": d.get("keywords", []),
            })

        user_prompt = (
            f"Generate a filter schema for these {len(summaries)} documents:\n\n"
            + json.dumps(summaries, indent=2)
        )

        result = self._call_llm(FILTER_SCHEMA_PROMPT, user_prompt, max_tokens=4000)
        return result

    def extract(self, documents: list[dict]) -> dict:
        """Full extraction: documents + filter schema.

        Returns:
            {
                "domain": str,
                "doc_extractions": [...],  # per-doc summary + keywords
                "dimensions": [...],       # filter schema dimensions
                "document_filters": [...]  # per-doc filter mappings
            }
        """
        # Phase 1
        doc_extractions = self.extract_documents(documents)
        logger.info(f"Phase 1: extracted metadata for {len(doc_extractions)} docs")

        # Phase 2
        schema = self.extract_filter_schema(doc_extractions)
        logger.info(f"Phase 2: domain='{schema.get('domain')}', "
                     f"dimensions={len(schema.get('dimensions', []))}")

        return {
            "domain": schema.get("domain", ""),
            "doc_extractions": doc_extractions,
            "dimensions": schema.get("dimensions", []),
            "document_filters": schema.get("document_filters", []),
        }


content_extraction_service = ContentExtractionService()
