import argparse
import os

from azure.identity import AzureCliCredential, ChainedTokenCredential, DefaultAzureCredential, get_bearer_token_provider

from content_understanding_client import AzureContentUnderstandingClient

# Get parameters from command line
p = argparse.ArgumentParser()
p.add_argument("--cu_endpoint", required=True)
p.add_argument("--cu_api_version", required=True)
args = p.parse_args()

CU_ENDPOINT = args.cu_endpoint
CU_API_VERSION = args.cu_api_version

ANALYZER_ID = "ckm-json"

ANALYZER_TEMPLATE_FILE = 'infra/data/ckm-analyzer_config_text.json'

credential = ChainedTokenCredential(
    AzureCliCredential(process_timeout=120),
    DefaultAzureCredential(
        exclude_cli_credential=True,
        exclude_shared_token_cache_credential=True,
        exclude_visual_studio_code_credential=True,
        exclude_interactive_browser_credential=True,
    ),
)
# Initialize Content Understanding Client
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
client = AzureContentUnderstandingClient(
    endpoint=CU_ENDPOINT,
    api_version=CU_API_VERSION,
    token_provider=token_provider
)

# Create Analyzer
try:
    analyzer = client.get_analyzer_detail_by_id(ANALYZER_ID)
    if analyzer is not None:
        client.delete_analyzer(ANALYZER_ID)
except Exception:  # Analyzer may not exist yet, safe to ignore
    pass

response = client.begin_create_analyzer(ANALYZER_ID, analyzer_template_path=ANALYZER_TEMPLATE_FILE)
result = client.poll_result(response)
print(f"✓ Analyzer '{ANALYZER_ID}' created")
