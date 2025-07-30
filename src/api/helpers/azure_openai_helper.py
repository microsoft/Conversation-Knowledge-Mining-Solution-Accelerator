
"""
Helper functions for initializing and managing Azure OpenAI client instances.
"""

import openai
from azure.identity import get_bearer_token_provider
from helpers.azure_credential_utils import get_azure_credential
from common.config.config import Config


def get_azure_openai_client():
    """
    Initializes and returns an Azure OpenAI client using a bearer token provider.
    """

    config = Config()
    token_provider = get_bearer_token_provider(
        get_azure_credential(), "https://cognitiveservices.azure.com/.default"
    )
    client = openai.AzureOpenAI(
        azure_endpoint=config.azure_openai_endpoint,
        api_version=config.azure_openai_api_version,
        azure_ad_token_provider=token_provider,
    )
    return client
