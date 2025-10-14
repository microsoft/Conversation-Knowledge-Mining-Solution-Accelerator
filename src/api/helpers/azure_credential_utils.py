import os
from azure.identity import ManagedIdentityCredential, AzureCliCredential
from azure.identity.aio import ManagedIdentityCredential as AioManagedIdentityCredential, AzureCliCredential as AioAzureCliCredential


async def get_azure_credential_async(client_id=None):
    """
    Returns an Azure credential asynchronously based on the application environment.

    If the environment is 'dev', it uses AioAzureCliCredential.
    Otherwise, it uses AioManagedIdentityCredential.

    Args:
        client_id (str, optional): The client ID for the Managed Identity Credential.

    Returns:
        Credential object: Either AioAzureCliCredential or AioManagedIdentityCredential.
    """
    if os.getenv("APP_ENV", "prod").lower() == 'dev':
        return AioAzureCliCredential()
    else:
        return AioManagedIdentityCredential(client_id=client_id)


def get_azure_credential(client_id=None):
    """
    Returns an Azure credential based on the application environment.

    If the environment is 'dev', it uses AzureCliCredential.
    Otherwise, it uses ManagedIdentityCredential.

    Args:
        client_id (str, optional): The client ID for the Managed Identity Credential.

    Returns:
        Credential object: Either AzureCliCredential or ManagedIdentityCredential.
    """
    if os.getenv("APP_ENV", "prod").lower() == 'dev':
        return AzureCliCredential()
    else:
        return ManagedIdentityCredential(client_id=client_id)
