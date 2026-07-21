from typing import Optional
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from src.api.config import get_settings

_client: Optional[AzureOpenAI] = None
_agent_chat_client: Optional[object] = None


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
                api_version=settings.azure_openai_api_version,
                timeout=settings.llm_request_timeout_sec,
            )
    return _client


def get_llm_chat_client():
    """Return an OpenAIChatCompletionClient compatible with agent_framework Agent.

    agent_framework requires its own BaseChatClient subclass — the raw AzureOpenAI
    client does not satisfy the get_response protocol. OpenAIChatCompletionClient
    from agent_framework_openai wraps AzureOpenAI and implements that protocol.
    """
    global _agent_chat_client
    if _agent_chat_client is None:
        from agent_framework_openai import OpenAIChatCompletionClient
        settings = get_settings()

        if settings.azure_foundry_endpoint:
            # Foundry path — reuse the underlying project client
            from azure.ai.projects import AIProjectClient
            credential = DefaultAzureCredential()
            project = AIProjectClient(
                endpoint=settings.azure_foundry_endpoint,
                credential=credential,
            )
            openai_client = project.inference.get_azure_openai_client()
            _agent_chat_client = OpenAIChatCompletionClient(
                model=settings.azure_openai_chat_deployment,
                async_client=openai_client,
            )
        else:
            # Direct Azure OpenAI path
            credential = DefaultAzureCredential()
            _agent_chat_client = OpenAIChatCompletionClient(
                model=settings.azure_openai_chat_deployment,
                azure_endpoint=settings.azure_openai_endpoint,
                credential=credential,
                api_version=settings.azure_openai_api_version,
            )
    return _agent_chat_client
