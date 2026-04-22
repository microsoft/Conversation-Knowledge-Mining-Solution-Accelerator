from typing import Optional
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from backend.config import get_settings

_client: Optional[AzureOpenAI] = None


def get_llm_client() -> AzureOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
        _client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-10-21",
        )
    return _client
