# === Imports ===
import sys
from pathlib import Path
import json

from azure.identity import get_bearer_token_provider
from azure.keyvault.secrets import SecretClient
from content_understanding_client import AzureContentUnderstandingClient
from azure_credential_utils import get_azure_credential
from azure.core.exceptions import HttpResponseError


# === Configuration ===
KEY_VAULT_NAME = 'kv-ckmpocdsapi15xyh6'
MANAGED_IDENTITY_CLIENT_ID = 'f6a5c843-6e09-4a87-a9f8-d12c9691ccfd'
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

"""
Resolve analyzer template path using this script's location to avoid cwd issues.
Script location: .../infra/scripts/index_scripts
Analyzer JSON:   .../infra/data/<file>
"""
script_dir = Path(__file__).resolve().parent
infra_dir = script_dir.parents[1]
data_dir = infra_dir / 'data'
template_path = Path(ANALYZER_TEMPLATE_FILE)
if not template_path.is_absolute():
    template_path = data_dir / ANALYZER_TEMPLATE_FILE

with open(template_path, 'r', encoding='utf-8') as f:
    _ = json.load(f)  # validate JSON exists and is readable

# Create Analyzer using explicit template path (API expects file path)
try:
    response = client.begin_create_analyzer(ANALYZER_ID, analyzer_template_path=str(template_path))
    result = client.poll_result(response)
except HttpResponseError as e:
    # Treat 409 Conflict (already exists) as success for idempotency
    status = getattr(e, 'status_code', None) or getattr(getattr(e, 'response', None), 'status_code', None)
    if status == 409 or 'Conflict' in str(e):
        print(f"Analyzer '{ANALYZER_ID}' already exists. Skipping creation.")
    else:
        raise
except Exception as e:
    # Some SDKs wrap the 409 in generic Exception; handle text check
    if '409' in str(e) or 'Conflict' in str(e):
        print(f"Analyzer '{ANALYZER_ID}' already exists. Skipping creation.")
    else:
        raise