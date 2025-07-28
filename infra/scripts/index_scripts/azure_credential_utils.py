from azure.identity import ManagedIdentityCredential, DefaultAzureCredential

APP_ENV = 'prod'  # Change to 'dev' for local development

def get_azure_credential(client_id=None):
    """
    Retrieves the appropriate Azure credential based on the application environment.

    If the application is running locally, it uses Azure CLI credentials.
    Otherwise, it uses a managed identity credential.

    Args:
        client_id (str, optional): The client ID for the managed identity. Defaults to None.

    Returns:
        azure.identity.DefaultAzureCredential or azure.identity.ManagedIdentityCredential: 
        The Azure credential object.
    """
    if APP_ENV == 'dev':
        return DefaultAzureCredential() # CodeQL [SM05139] Okay use of DefaultAzureCredential as it is only used in development
    else:
        return ManagedIdentityCredential(client_id=client_id)