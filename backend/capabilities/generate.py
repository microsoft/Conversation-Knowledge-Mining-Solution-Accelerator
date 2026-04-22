from backend.capabilities.registry import register
from backend.capabilities._llm import get_llm_client
from backend.config import get_settings


@register("generate")
def generate(prompt: str = "", system_prompt: str = "", temperature: float = 0.3, max_tokens: int = 1000, context: dict | None = None, **kwargs) -> dict:
    """Generate text using Azure OpenAI chat completion."""
    settings = get_settings()
    client = get_llm_client()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model=settings.azure_openai_chat_deployment,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return {"result": response.choices[0].message.content, "meta": {"model": settings.azure_openai_chat_deployment}}
