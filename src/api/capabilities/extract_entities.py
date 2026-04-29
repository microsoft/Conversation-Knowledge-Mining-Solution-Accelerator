import json
from src.api.capabilities.registry import register
from src.api.capabilities._llm import get_llm_client
from src.api.config import get_settings


@register("extract_entities")
def extract_entities(text: str | list[str] = "", schema: list[str] | None = None, context: dict | None = None, **kwargs) -> dict:
    """Extract entities from text. Accepts a single string or a list for batch."""
    if isinstance(text, list):
        results = [extract_entities(t, schema=schema) for t in text if t.strip()]
        return {"result": [r["result"] for r in results], "meta": {"count": len(results)}}

    settings = get_settings()
    type_instruction = (
        f"Extract these entity types: {', '.join(schema)}." if schema
        else "Extract all entities: Person, Organization, Product, Location, Date, Issue, Resolution, Policy, Amount, Reference Number."
    )
    client = get_llm_client()
    response = client.chat.completions.create(
        model=settings.azure_openai_chat_deployment,
        messages=[
            {"role": "system", "content": f"You are an entity extraction system. {type_instruction}\nReturn ONLY a JSON array of {{\"text\", \"type\", \"confidence\"}} objects."},
            {"role": "user", "content": text},
        ],
        temperature=0.1,
        max_tokens=1500,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        raw = raw.rsplit("```", 1)[0]
    try:
        entities = [e for e in json.loads(raw) if isinstance(e, dict) and e.get("text")]
    except json.JSONDecodeError:
        entities = []
    return {"result": entities, "meta": {"entity_count": len(entities)}}
