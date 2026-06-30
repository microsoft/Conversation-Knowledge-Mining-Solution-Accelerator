import argparse
import sys
from pathlib import Path

from azure.identity import AzureCliCredential, get_bearer_token_provider

from content_understanding_client import AzureContentUnderstandingClient

# Get parameters from command line
p = argparse.ArgumentParser()
p.add_argument("--cu_endpoint", required=True)
p.add_argument("--cu_api_version", required=True)
p.add_argument("--deployment_model", required=True)
p.add_argument("--embedding_model", required=True)
args = p.parse_args()

CU_ENDPOINT = args.cu_endpoint
CU_API_VERSION = args.cu_api_version

ANALYZER_ID = "ckm_analyzer_audio"

ANALYZER_TEMPLATE_FILE = 'infra/data/ckm_analyzer_config_audio.json'

# Add parent directory to path for imports
sys.path.append(str(Path.cwd().parent))

credential = AzureCliCredential(process_timeout=30)
# Initialize Content Understanding Client
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
client = AzureContentUnderstandingClient(
    endpoint=CU_ENDPOINT,
    api_version=CU_API_VERSION,
    token_provider=token_provider
)

# Set model defaults (mandatory for GA API)
client.set_defaults(args.deployment_model, args.embedding_model)

# Create Analyzer
try:
    analyzer = client.get_analyzer_detail_by_id(ANALYZER_ID)
    if analyzer is not None:
        client.delete_analyzer(ANALYZER_ID)
except Exception:  # Analyzer may not exist yet, safe to ignore
    pass

response = client.begin_create_analyzer(
    ANALYZER_ID,
    analyzer_template_path=ANALYZER_TEMPLATE_FILE,
    completion_model=args.deployment_model,
    embedding_model=args.embedding_model
)
result = client.poll_result(response)
print(f"✓ Analyzer '{ANALYZER_ID}' created")
