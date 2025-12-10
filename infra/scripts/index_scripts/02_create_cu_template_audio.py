from pathlib import Path
import sys

from azure.identity import get_bearer_token_provider, AzureCliCredential
from azure.keyvault.secrets import SecretClient

from content_understanding_client import AzureContentUnderstandingClient

KEY_VAULT_NAME=sys.argv[1]
AZURE_AI_API_VERSION = "2024-12-01-preview"
ANALYZER_ID = "ckm-audio"

ANALYZER_TEMPLATE_FILE = 'infra/data/ckm-analyzer_config_audio.json'

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
    kv_credential = AzureCliCredential()
    secret_client = SecretClient(
        vault_url=f"https://{vault_name}.vault.azure.net/",
        credential=kv_credential
    )
    return secret_client.get_secret(secret_name).value

# Add parent directory to path for module access
sys.path.append(str(Path.cwd().parent))
# Fetch endpoint from Key Vault
endpoint = get_secrets_from_kv("AZURE-OPENAI-CU-ENDPOINT", KEY_VAULT_NAME)

credential = AzureCliCredential()
# Initialize Content Understanding Client
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
client = AzureContentUnderstandingClient(
    endpoint=endpoint,
    api_version=AZURE_AI_API_VERSION,
    token_provider=token_provider
)

# Create Analyzer
try:
    analyzer = client.get_analyzer_detail_by_id(ANALYZER_ID)
    if analyzer is not None:
        client.delete_analyzer(ANALYZER_ID)
except Exception as e:
    print(f"Analyzer with ID {ANALYZER_ID} was not found. Proceeding to create a new one.")

response = client.begin_create_analyzer(ANALYZER_ID, analyzer_template_path=ANALYZER_TEMPLATE_FILE)
result = client.poll_result(response)
print(f"Analyzer with ID {ANALYZER_ID} created successfully.")
