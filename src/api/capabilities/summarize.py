from src.api.capabilities.registry import register
from src.api.capabilities._llm import get_llm_client
from src.api.config import get_settings


@register("summarize")
def summarize(text: str | list[str] = "", style: str = "concise", max_length: int = 200, context: dict | None = None, **kwargs) -> dict:
    """Summarize text. Accepts a single string or a list for batch."""
    if isinstance(text, list):
        results = [summarize(t, style=style, max_length=max_length) for t in text if t.strip()]
        return {"result": [r["result"] for r in results], "meta": {"count": len(results), "style": style}}

    settings = get_settings()
    prompts = {
        "concise": f"Summarize in {max_length} words or fewer. Be direct.",
        "detailed": f"Provide a detailed summary in about {max_length} words.",
        "bullet_points": f"Summarize as bullet points. Max {max_length} words.",
        "executive": f"Write an executive summary in {max_length} words.",
    }
    client = get_llm_client()
    response = client.chat.completions.create(
        model=settings.azure_openai_chat_deployment,
        messages=[
            {"role": "system", "content": prompts.get(style, prompts["concise"])},
            {"role": "user", "content": text},
        ],
        temperature=0.3,
        max_tokens=max_length * 2,
    )
    return {"result": response.choices[0].message.content, "meta": {"style": style, "original_length": len(text.split())}}
