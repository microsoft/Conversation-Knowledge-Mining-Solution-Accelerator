from src.api.capabilities.registry import register
from src.api.capabilities._llm import get_llm_client
from src.api.config import get_settings


@register("classify")
def classify(text: str = "", labels: list[str] | None = None, context: dict | None = None, **kwargs) -> dict:
    """Classify text into one of the provided labels using LLM."""
    if not labels:
        labels = ["general"]
    settings = get_settings()
    client = get_llm_client()
    response = client.chat.completions.create(
        model=settings.azure_openai_chat_deployment,
        messages=[
            {
                "role": "system",
                "content": (
                    f"Classify the following text into exactly one of these categories: {', '.join(labels)}.\n"
                    "Return ONLY a JSON object with 'label' and 'confidence' (0-1) fields."
                ),
            },
            {"role": "user", "content": text},
        ],
        temperature=0.1,
        max_tokens=100,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        raw = raw.rsplit("```", 1)[0]
    import json
    try:
        parsed = json.loads(raw)
        return {"result": parsed.get("label", "unknown"), "meta": {"confidence": parsed.get("confidence", 0)}}
    except json.JSONDecodeError:
        return {"result": raw.strip(), "meta": {"confidence": 0}}
