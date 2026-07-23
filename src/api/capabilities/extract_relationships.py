"""LLM-powered semantic relationship extraction capability.

Extracts (subject → relation → object) triples from text and returns
them in the format expected by save_entity_graph().
"""

import json

from src.api.capabilities.registry import register
from src.api.capabilities._llm import get_llm_client
from src.api.config import get_settings
from src.api.utils.constants import strip_code_fences


@register("extract_relationships")
def extract_relationships(text: str = "", context: dict | None = None, **kwargs) -> dict:
    """Extract semantic relationships between named entities from text.

    Returns a list of dicts with keys:
      subject, subject_type, relation, object, object_type, confidence, context
    """
    if not text or not text.strip():
        return {"result": [], "meta": {"count": 0}}

    settings = get_settings()
    client = get_llm_client()

    response = client.chat.completions.create(
        model=settings.azure_openai_chat_deployment,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a relationship extraction system. Given a text, extract meaningful "
                    "semantic relationships between named entities (people, organizations, locations, "
                    "products, policies, dates, amounts, etc.).\n\n"
                    "Return ONLY a JSON array of objects with exactly these fields:\n"
                    '  "subject"      – source entity name (string)\n'
                    '  "subject_type" – entity type of subject (string)\n'
                    '  "relation"     – concise verb phrase (e.g. "owns", "signed", "is located in")\n'
                    '  "object"       – target entity name or value (string)\n'
                    '  "object_type"  – entity type of object (string)\n'
                    '  "confidence"   – 0.0–1.0 float\n'
                    '  "context"      – short evidence snippet from the text (max 200 chars)\n\n'
                    "Rules:\n"
                    "- Only extract relationships explicitly stated or strongly implied\n"
                    "- Use concise verb phrases; avoid generic phrases like 'is related to'\n"
                    "- Return at most 15 relationships; minimum confidence 0.5\n"
                    "- Return [] if no meaningful relationships found"
                ),
            },
            {"role": "user", "content": text[:6000]},
        ],
        temperature=0.1,
        max_completion_tokens=2000,
    )

    raw = (response.choices[0].message.content or "").strip()
    raw = strip_code_fences(raw)
    try:
        rels = [
            r for r in json.loads(raw)
            if isinstance(r, dict)
            and r.get("subject")
            and r.get("relation")
            and r.get("object")
            and float(r.get("confidence", 0)) >= 0.5
        ]
    except (json.JSONDecodeError, ValueError):
        rels = []

    return {"result": rels, "meta": {"count": len(rels)}}
