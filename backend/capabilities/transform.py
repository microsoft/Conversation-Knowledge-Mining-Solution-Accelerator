from backend.capabilities.registry import register
from backend.capabilities._llm import get_llm_client
from backend.config import get_settings

VALID_MODES = {
    "normalize": "Clean and normalize this text. Fix grammar, remove artifacts, standardize formatting.",
    "translate": "Translate this text to {target_lang}. Preserve meaning exactly.",
    "tone": "Rewrite this text in a {tone} tone. Preserve all information.",
    "simplify": "Simplify this text to be easily understood by a general audience.",
    "expand": "Expand this text with more detail while preserving the original meaning.",
}


@register("transform")
def transform(text: str = "", mode: str = "normalize", target_lang: str = "en", tone: str = "formal", context: dict | None = None, **kwargs) -> dict:
    """Structured text transformation. No free-form instructions allowed."""
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Valid: {sorted(VALID_MODES.keys())}")

    instruction = VALID_MODES[mode].format(target_lang=target_lang, tone=tone)

    settings = get_settings()
    client = get_llm_client()
    response = client.chat.completions.create(
        model=settings.azure_openai_chat_deployment,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": text},
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    return {"result": response.choices[0].message.content, "meta": {"mode": mode}}
