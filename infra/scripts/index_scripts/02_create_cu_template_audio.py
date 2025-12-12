import argparse
import sys
from pathlib import Path

from azure.identity import AzureCliCredential, get_bearer_token_provider

from content_understanding_client import AzureContentUnderstandingClient

# Get parameters from command line
p = argparse.ArgumentParser()
p.add_argument("--cu_endpoint", required=True)
p.add_argument("--cu_api_version", required=True)
args = p.parse_args()

CU_ENDPOINT = args.cu_endpoint
CU_API_VERSION = args.cu_api_version

ANALYZER_ID = "ckm-audio"

ANALYZER_TEMPLATE_FILE = 'infra/data/ckm-analyzer_config_audio.json'

# Add parent directory to path for imports
sys.path.append(str(Path.cwd().parent))

credential = AzureCliCredential()
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
except Exception as e:
    print(f"Analyzer with ID {ANALYZER_ID} was not found. Proceeding to create a new one.")

response = client.begin_create_analyzer(ANALYZER_ID, analyzer_template_path=ANALYZER_TEMPLATE_FILE)
result = client.poll_result(response)
print(f"Analyzer with ID {ANALYZER_ID} created successfully.")
