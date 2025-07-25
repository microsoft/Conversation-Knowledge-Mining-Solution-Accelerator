from pathlib import Path
import sys

from azure.identity import ManagedIdentityCredential, AzureCliCredential, CredentialUnavailableError, get_bearer_token_provider
from azure.keyvault.secrets import SecretClient

from content_understanding_client import AzureContentUnderstandingClient


# === Configuration ===
KEY_VAULT_NAME = 'kv_to-be-replaced'
MANAGED_IDENTITY_CLIENT_ID = 'mici_to-be-replaced'
AZURE_AI_API_VERSION = "2024-12-01-preview"
ANALYZER_ID = "ckm-audio"
ANALYZER_TEMPLATE_FILE = 'ckm-analyzer_config_audio.json'

def get_credential():
    try:
        mi_credential = ManagedIdentityCredential(client_id=MANAGED_IDENTITY_CLIENT_ID)
        mi_credential.get_token("https://management.azure.com/.default")
        return mi_credential
    except Exception as mi_error:
        try:
            cli_credential = AzureCliCredential()
            cli_credential.get_token("https://management.azure.com/.default")
            return cli_credential
        except Exception as cli_error:
            raise CredentialUnavailableError(
                f"Failed to obtain credentials. ManagedIdentityCredential error: {mi_error}. AzureCliCredential error: {cli_error}"
            ) from cli_error

# === Helper Functions ===
def get_secrets_from_kv(secret_name: str, vault_name: str) -> str:
    """
    Retrieve a secret value from Azure Key Vault.

    Args:
        secret_name (str): The name of the secret to retrieve.
        vault_name (str): The name of the Azure Key Vault.

    Returns:
        str: The value of the secret.
    """
    kv_credential = get_credential()
    secret_client = SecretClient(
        vault_url=f"https://{vault_name}.vault.azure.net/",
        credential=kv_credential
    )
    return secret_client.get_secret(secret_name).value

# Add parent directory to path for module access
sys.path.append(str(Path.cwd().parent))
# Fetch endpoint from Key Vault
endpoint = get_secrets_from_kv("AZURE-OPENAI-CU-ENDPOINT", KEY_VAULT_NAME)

credential = get_credential()
# Initialize Content Understanding Client
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
client = AzureContentUnderstandingClient(
    endpoint=endpoint,
    api_version=AZURE_AI_API_VERSION,
    token_provider=token_provider
)

# Create Analyzer
response = client.begin_create_analyzer(ANALYZER_ID, analyzer_template_path=ANALYZER_TEMPLATE_FILE)
result = client.poll_result(response)