# === Imports ===
import sys
from pathlib import Path

from azure.identity import get_bearer_token_provider
from azure.keyvault.secrets import SecretClient
from content_understanding_client import AzureContentUnderstandingClient
from azure_credential_utils import get_azure_credential


# === Configuration ===
KEY_VAULT_NAME = 'kv_to-be-replaced'
MANAGED_IDENTITY_CLIENT_ID = 'mici_to-be-replaced'
AZURE_AI_API_VERSION = "2024-12-01-preview"
ANALYZER_ID = "ckm-json"
ANALYZER_TEMPLATE_FILE = 'ckm-analyzer_config_text.json'


# === Helper Functions ===
def get_secret(secret_name: str, vault_name: str) -> str:
    """
    Retrieve a secret value from Azure Key Vault.
    """
    kv_credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
    secret_client = SecretClient(vault_url=f"https://{vault_name}.vault.azure.net/", credential=kv_credential)
    return secret_client.get_secret(secret_name).value


# Add parent directory to import local modules
sys.path.append(str(Path.cwd().parent))
# Get endpoint from Key Vault
endpoint = get_secret("AZURE-OPENAI-CU-ENDPOINT", KEY_VAULT_NAME)

credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
# Initialize Content Understanding Client
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
client = AzureContentUnderstandingClient(
    endpoint=endpoint,
    api_version=AZURE_AI_API_VERSION,
    token_provider=token_provider
)

# Create Analyzer
if __name__ == "__main__":
    try:
        print(f"Creating analyzer '{ANALYZER_ID}' from template '{ANALYZER_TEMPLATE_FILE}'...")
        response = client.begin_create_analyzer(ANALYZER_ID, analyzer_template_path=ANALYZER_TEMPLATE_FILE)
        result = client.poll_result(response)
        print(f"Analyzer '{ANALYZER_ID}' created successfully.")
        print("Script completed successfully.")
    except Exception as e:
        print(f"ERROR: Script failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)