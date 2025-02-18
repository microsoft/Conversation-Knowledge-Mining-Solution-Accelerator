# Import required modules


from azure.keyvault.secrets import SecretClient  
from azure.identity import DefaultAzureCredential
import sys
from pathlib import Path
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

key_vault_name = 'kv_to-be-replaced'

def get_secrets_from_kv(kv_name, secret_name):

    # Set the name of the Azure Key Vault  
    key_vault_name = kv_name 
    credential = DefaultAzureCredential()

    # Create a secret client object using the credential and Key Vault name  
    secret_client =  SecretClient(vault_url=f"https://{key_vault_name}.vault.azure.net/", credential=credential)  

    # Retrieve the secret value  
    return(secret_client.get_secret(secret_name).value)


# Add the parent directory to the path to use shared modules
parent_dir = Path(Path.cwd()).parent
sys.path.append(str(parent_dir))
from content_understanding_client import AzureContentUnderstandingClient
AZURE_AI_ENDPOINT = get_secrets_from_kv(key_vault_name,"AZURE-OPENAI-CU-ENDPOINT")
AZURE_OPENAI_CU_KEY = get_secrets_from_kv(key_vault_name,"AZURE-OPENAI-CU-KEY")
AZURE_AI_API_VERSION = "2024-12-01-preview" 


credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

client = AzureContentUnderstandingClient(
    endpoint=AZURE_AI_ENDPOINT,
    api_version=AZURE_AI_API_VERSION,
    subscription_key=AZURE_OPENAI_CU_KEY,
    token_provider=token_provider
)


ANALYZER_ID = "ckm-audio"
ANALYZER_TEMPLATE_FILE = 'ckm-analyzer_config_audio.json'


# Create analyzer
response = client.begin_create_analyzer(ANALYZER_ID, analyzer_template_path=ANALYZER_TEMPLATE_FILE)
result = client.poll_result(response)