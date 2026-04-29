from src.api.capabilities.registry import register
from src.api.capabilities._llm import get_llm_client
from src.api.config import get_settings


@register("embed")
def embed(text: str = "", context: dict | None = None, **kwargs) -> dict:
    """Generate embedding vector for text using Azure OpenAI."""
    settings = get_settings()
    client = get_llm_client()
    response = client.embeddings.create(input=text, model=settings.azure_openai_embedding_deployment)
    embedding = response.data[0].embedding
    return {"result": embedding, "meta": {"dimensions": len(embedding), "model": settings.azure_openai_embedding_deployment}}
