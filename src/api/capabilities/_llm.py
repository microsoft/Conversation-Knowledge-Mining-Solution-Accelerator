from typing import Optional
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from src.api.config import get_settings

_client: Optional[AzureOpenAI] = None


def get_llm_client() -> AzureOpenAI:
    """Return a singleton AzureOpenAI client.

    If azure_foundry_endpoint is configured, the client is obtained via
    AIProjectClient (Foundry IQ) — centralizing model governance, tracing,
    and quota management through a single Foundry Project.

    Falls back to direct AzureOpenAI construction when Foundry IQ is not set.
    """
    global _client
    if _client is None:
        settings = get_settings()

        if settings.azure_foundry_endpoint:
            # Foundry IQ path — single project governs all model access
            from azure.ai.projects import AIProjectClient

            credential = DefaultAzureCredential()
            project = AIProjectClient(
                endpoint=settings.azure_foundry_endpoint,
                credential=credential,
            )
            _client = project.inference.get_azure_openai_client()
        else:
            # Direct Azure OpenAI SDK fallback
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
            _client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version="2024-10-21",
            )
    return _client
