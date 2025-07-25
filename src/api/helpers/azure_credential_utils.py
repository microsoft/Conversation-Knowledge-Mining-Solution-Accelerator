from azure.identity import ManagedIdentityCredential, AzureCliCredential
from azure.identity.aio import ManagedIdentityCredential as AioManagedIdentityCredential, AzureCliCredential as AioAzureCliCredential

async def get_azure_credential_async(client_id=None):
    """
    Returns an Azure credential asynchronously, falling back to AioAzureCliCredential if AioManagedIdentityCredential fails.

    Args:
        client_id (str, optional): The client ID for the Managed Identity Credential.

    Returns:
        Credential object: Either AioManagedIdentityCredential or AioAzureCliCredential.
    """
    try:
        mi_credential = AioManagedIdentityCredential(client_id=client_id)
        await mi_credential.get_token("https://management.azure.com/.default")
        return mi_credential
    except Exception:
        try:
            cli_credential = AioAzureCliCredential()
            await cli_credential.get_token("https://management.azure.com/.default")
            return cli_credential
        except Exception:
            raise Exception("Failed to obtain credentials using ManagedIdentityCredential and AzureCliCredential.")

def get_azure_credential(client_id=None):
    """
    Returns an Azure credential, falling back to AzureCliCredential if ManagedIdentityCredential fails.

    Args:
        client_id (str, optional): The client ID for the Managed Identity Credential.

    Returns:
        Credential object: Either ManagedIdentityCredential or AzureCliCredential.
    """
    try:
        mi_credential = ManagedIdentityCredential(client_id=client_id)
        mi_credential.get_token("https://management.azure.com/.default")
        return mi_credential
    except Exception:
        try:
            cli_credential = AzureCliCredential()
            cli_credential.get_token("https://management.azure.com/.default")
            return cli_credential
        except Exception:
            raise Exception("Failed to obtain credentials using ManagedIdentityCredential and AzureCliCredential.")


