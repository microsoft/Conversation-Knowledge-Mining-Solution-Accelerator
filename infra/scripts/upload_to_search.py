import os
import sys
import json

# Load .env
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
env_path = os.path.join(project_root, ".env")

if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().split("#")[0].strip()  # remove inline comments
                if key and value:
                    os.environ.setdefault(key, value)

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
)

# ============================================================================
# Configuration
# ============================================================================

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "knowledge-mining-index")
STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT", "bskmstorage12345")
STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "documents")

if not SEARCH_ENDPOINT:
    print("ERROR: AZURE_SEARCH_ENDPOINT not set in .env")
    sys.exit(1)

STORAGE_URL = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net"

# Load dataset
data_path = os.path.join(project_root, "Sample_Data", "Customer_service_data.json")
if not os.path.exists(data_path):
    print(f"ERROR: Dataset not found at {data_path}")
    sys.exit(1)

with open(data_path, encoding="utf-8") as f:
    documents = json.load(f)

print(f"Loaded {len(documents)} documents from dataset")

credential = DefaultAzureCredential()

# ============================================================================
# Step 1: Upload to Azure Blob Storage
# ============================================================================

def upload_to_blob_storage():
    """Upload each document as a JSON blob."""
    print(f"\n{'='*60}")
    print(f"Step 1: Upload to Azure Blob Storage")
    print(f"{'='*60}")
    print(f"Storage: {STORAGE_URL}")
    print(f"Container: {STORAGE_CONTAINER}")

    blob_service = BlobServiceClient(account_url=STORAGE_URL, credential=credential)

    # Create container if it doesn't exist
    try:
        container_client = blob_service.get_container_client(STORAGE_CONTAINER)
        if not container_client.exists():
            container_client.create_container()
            print(f"[OK] Created container '{STORAGE_CONTAINER}'")
        else:
            print(f"[OK] Container '{STORAGE_CONTAINER}' exists")
    except Exception as e:
        print(f"[WARN] Container check failed: {e}")
        try:
            blob_service.create_container(STORAGE_CONTAINER)
            print(f"[OK] Created container '{STORAGE_CONTAINER}'")
        except Exception:
            pass
        container_client = blob_service.get_container_client(STORAGE_CONTAINER)

    uploaded = 0
    for doc in documents:
        blob_name = f"{doc['id']}.json"
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(
            json.dumps(doc, indent=2),
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json"),
        )
        uploaded += 1

    print(f"[OK] Uploaded {uploaded} documents to blob storage")
    return uploaded


# ============================================================================
# Step 2: Create Azure AI Search Index
# ============================================================================

def create_search_index():
    """Create the search index with the correct schema."""
    print(f"\n{'='*60}")
    print(f"Step 2: Create Azure AI Search Index")
    print(f"{'='*60}")
    print(f"Search: {SEARCH_ENDPOINT}")
    print(f"Index: {INDEX_NAME}")

    index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=credential)

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchableField(name="text", type=SearchFieldDataType.String),
        SimpleField(name="type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="product", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="timestamp", type=SearchFieldDataType.String, filterable=True, sortable=True),
    ]

    index = SearchIndex(name=INDEX_NAME, fields=fields)

    try:
        result = index_client.create_or_update_index(index)
        print(f"[OK] Index '{result.name}' created/updated")
        print(f"  Fields: {', '.join(f.name for f in result.fields)}")
    except Exception as e:
        print(f"[FAIL] Failed to create index: {e}")
        sys.exit(1)

    return result


# ============================================================================
# Step 3: Index Documents into Azure AI Search
# ============================================================================

def index_documents():
    """Upload all documents to the search index."""
    print(f"\n{'='*60}")
    print(f"Step 3: Index Documents")
    print(f"{'='*60}")

    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=credential,
    )

    # Prepare documents for indexing
    search_docs = []
    for doc in documents:
        text = doc.get("text", "")
        if isinstance(text, list):
            # Audio transcript with speaker segments
            text = "\n".join(f"{seg.get('speaker', 'Unknown')}: {seg.get('text', '')}" for seg in text)

        search_docs.append({
            "id": doc["id"],
            "text": text,
            "type": doc.get("type", "unknown"),
            "product": doc.get("metadata", {}).get("product", ""),
            "category": doc.get("metadata", {}).get("category", ""),
            "timestamp": doc.get("metadata", {}).get("timestamp", ""),
        })

    # Upload in batches of 100
    batch_size = 100
    indexed = 0
    errors = []
    for i in range(0, len(search_docs), batch_size):
        batch = search_docs[i:i + batch_size]
        try:
            result = search_client.upload_documents(documents=batch)
            for r in result:
                if r.succeeded:
                    indexed += 1
                else:
                    errors.append(f"{r.key}: {r.error_message}")
        except Exception as e:
            print(f"[FAIL] Batch upload failed: {e}")
            errors.append(str(e))

    print(f"[OK] Indexed {indexed}/{len(search_docs)} documents")
    if errors:
        print(f"[WARN] {len(errors)} errors:")
        for err in errors[:5]:
            print(f"  - {err}")

    return indexed


# ============================================================================
# Run
# ============================================================================

if __name__ == "__main__":
    print(f"\nKnowledge Mining - Upload & Index Pipeline")
    print(f"Documents: {len(documents)}")

    try:
        upload_to_blob_storage()
    except Exception as e:
        print(f"[WARN] Blob upload failed: {e}")
        print("  Skipping blob upload — continuing with search indexing...")
        print("  To fix: assign 'Storage Blob Data Contributor' role to your account")
    create_search_index()
    indexed = index_documents()

    print(f"\n{'='*60}")
    print(f"Done!")
    print(f"{'='*60}")
    print(f"  Blob Storage: {STORAGE_URL}/{STORAGE_CONTAINER}/ ({len(documents)} blobs)")
    print(f"  Search Index: {INDEX_NAME} ({indexed} documents)")
 
