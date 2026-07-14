"""Upload sample data to Azure AI Search and Cosmos DB after azd deployment.

Uploads:
  - sample_search_index_data.json       → Azure AI Search index
  - sample_processed_data.json          → Cosmos DB 'documents' container
  - sample_processed_data_key_phrases.json → Cosmos DB 'key_phrases' container

Prerequisites:
  - Run `azd up` first (creates .env with connection details)
  - Your Azure identity must have:
      • Search Index Data Contributor on the AI Search resource
      • Cosmos DB Built-in Data Contributor on the Cosmos account
"""

import os
import sys
import json

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
env_path = os.path.join(project_root, ".env")

if os.path.exists(env_path):
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().split("#")[0].strip()
                if key and value:
                    os.environ.setdefault(key, value)
else:
    print("WARNING: .env file not found — using existing environment variables")

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)
from azure.cosmos import CosmosClient, PartitionKey

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "knowledge-mining-index")
OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
COSMOS_ENDPOINT = os.getenv("AZURE_COSMOS_ENDPOINT", "")
COSMOS_DATABASE = os.getenv("AZURE_COSMOS_DATABASE", "km-db")
SQL_SERVER = os.getenv("AZURE_SQL_SERVER", "")
SQL_DATABASE = os.getenv("AZURE_SQL_DATABASE", "km-db")

DATA_DIR = os.getenv("KM_SCENARIO_DATA_DIR", os.path.join(project_root, "data", "ContactCenter_usecase"))

SEARCH_DATA_FILE = os.path.join(DATA_DIR, "sample_search_index_data.json")
PROCESSED_DATA_FILE = os.path.join(DATA_DIR, "sample_processed_data.json")
KEY_PHRASES_FILE = os.path.join(DATA_DIR, "sample_processed_data_key_phrases.json")

credential = DefaultAzureCredential()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_json(path: str) -> list[dict]:
    if not os.path.exists(path):
        print(f"  ERROR: File not found: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Step 1 — Azure AI Search
# ---------------------------------------------------------------------------
def ensure_search_index():
    """Create or update the search index with vector search support."""
    print(f"\n{'='*60}")
    print("Step 1: Ensure Azure AI Search index exists")
    print(f"{'='*60}")
    print(f"  Endpoint : {SEARCH_ENDPOINT}")
    print(f"  Index    : {INDEX_NAME}")

    index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=credential)

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm_configuration_name="hnsw-config",
                vectorizer_name="openai-vectorizer",
            )
        ],
        vectorizers=[
            AzureOpenAIVectorizer(
                vectorizer_name="openai-vectorizer",
                kind="azureOpenAI",
                parameters=AzureOpenAIVectorizerParameters(
                    resource_url=OPENAI_ENDPOINT,
                    deployment_name=EMBEDDING_MODEL,
                    model_name=EMBEDDING_MODEL,
                ),
            )
        ],
    )

    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="summary"),
                    keywords_fields=[SemanticField(field_name="key_phrases")],
                    content_fields=[SemanticField(field_name="text")],
                ),
            )
        ]
    )

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SimpleField(name="doc_id", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SearchableField(name="text", type=SearchFieldDataType.String),
        SearchableField(name="summary", type=SearchFieldDataType.String),
        SimpleField(name="type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="product", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="timestamp", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="source_file", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="key_phrases", type=SearchFieldDataType.String, collection=True, filterable=True),
        SearchableField(name="entities", type=SearchFieldDataType.String, collection=True, filterable=True),
        SearchableField(name="topics", type=SearchFieldDataType.String, collection=True, filterable=True),
        SearchField(
            name="text_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="vector-profile",
        ),
    ]

    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )
    result = index_client.create_or_update_index(index)
    print(f"  [OK] Index '{result.name}' ready ({len(result.fields)} fields)")


def upload_search_data():
    """Upload sample_search_index_data.json to Azure AI Search with field mapping."""
    print(f"\n{'='*60}")
    print("Step 2: Upload documents to Azure AI Search")
    print(f"{'='*60}")

    raw_docs = load_json(SEARCH_DATA_FILE)
    print(f"  Loaded {len(raw_docs)} documents from {os.path.basename(SEARCH_DATA_FILE)}")

    # Map fields from sample data format → app index schema
    mapped = []
    for doc in raw_docs:
        mapped.append({
            "id": doc["id"],
            "text": doc.get("content", ""),
            "text_vector": doc.get("contentVector", []),
            "source_file": doc.get("sourceurl", ""),
            "doc_id": doc.get("chunk_id", "").rsplit("_", 1)[0] if doc.get("chunk_id") else "",
        })

    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=credential,
    )

    # Upload in batches of 50
    batch_size = 50
    uploaded = 0
    errors = []
    for i in range(0, len(mapped), batch_size):
        batch = mapped[i : i + batch_size]
        result = search_client.upload_documents(documents=batch)
        for r in result:
            if r.succeeded:
                uploaded += 1
            else:
                errors.append(f"  {r.key}: {r.error_message}")

    print(f"  [OK] Indexed {uploaded}/{len(mapped)} documents")
    if errors:
        print(f"  [WARN] {len(errors)} errors:")
        for e in errors[:5]:
            print(f"    {e}")


# ---------------------------------------------------------------------------
# Step 3 — Cosmos DB: processed data
# ---------------------------------------------------------------------------
def upload_processed_data():
    """Upload sample_processed_data.json to Cosmos DB 'documents' container."""
    print(f"\n{'='*60}")
    print("Step 3: Upload processed data to Cosmos DB")
    print(f"{'='*60}")
    print(f"  Endpoint : {COSMOS_ENDPOINT}")
    print(f"  Database : {COSMOS_DATABASE}")

    client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
    db = client.create_database_if_not_exists(COSMOS_DATABASE)
    container = db.create_container_if_not_exists(
        id="documents",
        partition_key=PartitionKey(path="/id"),
    )

    raw_docs = load_json(PROCESSED_DATA_FILE)
    print(f"  Loaded {len(raw_docs)} documents from {os.path.basename(PROCESSED_DATA_FILE)}")

    uploaded = 0
    for doc in raw_docs:
        item = {
            "id": doc["ConversationId"],
            "doc_type": "call_transcript",
            "text_content": doc.get("Content", ""),
            "summary": doc.get("summary", ""),
            "sentiment": doc.get("sentiment", ""),
            "topic": doc.get("topic", ""),
            "key_phrases": doc.get("key_phrases", ""),
            "complaint": doc.get("complaint", ""),
            "mined_topic": doc.get("mined_topic", ""),
            "satisfied": doc.get("satisfied", ""),
            "start_time": doc.get("StartTime", ""),
            "end_time": doc.get("EndTime", ""),
        }
        container.upsert_item(item)
        uploaded += 1

    print(f"  [OK] Upserted {uploaded} documents")


# ---------------------------------------------------------------------------
# Step 4 — Cosmos DB: key phrases
# ---------------------------------------------------------------------------
def upload_key_phrases():
    """Upload sample_processed_data_key_phrases.json to Cosmos DB 'key_phrases' container."""
    print(f"\n{'='*60}")
    print("Step 4: Upload key phrases to Cosmos DB")
    print(f"{'='*60}")

    client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
    db = client.create_database_if_not_exists(COSMOS_DATABASE)
    container = db.create_container_if_not_exists(
        id="key_phrases",
        partition_key=PartitionKey(path="/ConversationId"),
    )

    raw_docs = load_json(KEY_PHRASES_FILE)
    print(f"  Loaded {len(raw_docs)} key phrases from {os.path.basename(KEY_PHRASES_FILE)}")

    uploaded = 0
    for i, doc in enumerate(raw_docs):
        item = {
            "id": f"{doc['ConversationId']}_{i}",
            "ConversationId": doc["ConversationId"],
            "key_phrase": doc.get("key_phrase", ""),
            "sentiment": doc.get("sentiment", ""),
            "topic": doc.get("topic", ""),
            "start_time": doc.get("StartTime", ""),
        }
        container.upsert_item(item)
        uploaded += 1
        if uploaded % 200 == 0:
            print(f"    ... {uploaded}/{len(raw_docs)}")

    print(f"  [OK] Upserted {uploaded} key phrases")


# ---------------------------------------------------------------------------
# Step 5 — Azure SQL: documents table (powers the insights dashboard)
# ---------------------------------------------------------------------------
def upload_to_sql():
    """Upload processed data to Azure SQL documents table for dashboard analytics."""
    print(f"\n{'='*60}")
    print("Step 5: Upload processed data to Azure SQL")
    print(f"{'='*60}")
    print(f"  Server   : {SQL_SERVER}")
    print(f"  Database : {SQL_DATABASE}")

    import struct
    import pyodbc

    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={SQL_SERVER};"
        f"Database={SQL_DATABASE};"
        f"Encrypt=yes;TrustServerCertificate=no;"
    )
    conn = pyodbc.connect(conn_str, attrs_before={1256: token_struct})
    cursor = conn.cursor()

    # Ensure table exists (same schema as sql_service.py)
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'documents')
        CREATE TABLE documents (
            id NVARCHAR(255) PRIMARY KEY,
            doc_type NVARCHAR(50),
            text_content NVARCHAR(MAX),
            summary NVARCHAR(MAX),
            entities NVARCHAR(MAX),
            key_phrases NVARCHAR(MAX),
            topics NVARCHAR(MAX),
            metadata NVARCHAR(MAX),
            source_file NVARCHAR(500),
            created_at DATETIME2 DEFAULT GETUTCDATE()
        )
    """)
    conn.commit()

    raw_docs = load_json(PROCESSED_DATA_FILE)
    source_filename = os.path.basename(PROCESSED_DATA_FILE)
    print(f"  Loaded {len(raw_docs)} documents from {os.path.basename(PROCESSED_DATA_FILE)}")

    uploaded = 0
    for doc in raw_docs:
        kp_str = doc.get("key_phrases", "")
        kp_list = [p.strip() for p in kp_str.split(",") if p.strip()] if isinstance(kp_str, str) else kp_str
        metadata = {
            "sentiment": doc.get("sentiment", ""),
            "satisfied": doc.get("satisfied", ""),
            "topic": doc.get("topic", ""),
            "complaint": doc.get("complaint", ""),
            "mined_topic": doc.get("mined_topic", ""),
            "start_time": doc.get("StartTime", ""),
            "end_time": doc.get("EndTime", ""),
            "source_file": source_filename,
        }
        cursor.execute("""
            MERGE documents AS target
            USING (SELECT ? AS id) AS source ON target.id = source.id
            WHEN MATCHED THEN UPDATE SET
                doc_type=?, text_content=?, summary=?,
                key_phrases=?, topics=?, metadata=?, source_file=?
            WHEN NOT MATCHED THEN INSERT
                (id, doc_type, text_content, summary, key_phrases, topics, metadata, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
            doc["ConversationId"],
            "call_transcript", doc.get("Content", ""), doc.get("summary", ""),
            json.dumps(kp_list), json.dumps([doc.get("mined_topic", "")]),
            json.dumps(metadata), source_filename,
            # INSERT values
            doc["ConversationId"],
            "call_transcript", doc.get("Content", ""), doc.get("summary", ""),
            json.dumps(kp_list), json.dumps([doc.get("mined_topic", "")]),
            json.dumps(metadata), source_filename,
        )
        uploaded += 1

    conn.commit()
    conn.close()
    print(f"  [OK] Upserted {uploaded} documents")


# ---------------------------------------------------------------------------
# Step 5b — Azure SQL: uploaded_files entry (so the app shows the file)
# ---------------------------------------------------------------------------
def register_uploaded_file():
    """Register a file entry in uploaded_files so the app UI shows the data."""
    import struct
    import pyodbc

    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={SQL_SERVER};"
        f"Database={SQL_DATABASE};"
        f"Encrypt=yes;TrustServerCertificate=no;"
    )
    conn = pyodbc.connect(conn_str, attrs_before={1256: token_struct})
    cursor = conn.cursor()

    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'uploaded_files')
        CREATE TABLE uploaded_files (
            id NVARCHAR(255) PRIMARY KEY,
            filename NVARCHAR(500),
            doc_count INT,
            summary NVARCHAR(MAX),
            keywords NVARCHAR(MAX),
            filter_values NVARCHAR(MAX),
            uploaded_at NVARCHAR(100)
        )
    """)

    raw_docs = load_json(PROCESSED_DATA_FILE)
    doc_ids = [d["ConversationId"] for d in raw_docs]
    file_id = "sample-call-transcripts"
    filename = "sample_processed_data.json"

    cursor.execute("""
        MERGE uploaded_files AS target
        USING (SELECT ? AS id) AS source ON target.id = source.id
        WHEN MATCHED THEN UPDATE SET
            filename=?, doc_count=?, summary=?, keywords=?, filter_values=?, uploaded_at=?
        WHEN NOT MATCHED THEN INSERT
            (id, filename, doc_count, summary, keywords, filter_values, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
    """,
        file_id,
        filename, len(doc_ids),
        f"{len(doc_ids)} sample call transcripts",
        json.dumps(["call transcript", "sample data"]),
        json.dumps({}),
        "2025-12-08T00:00:00Z",
        # INSERT values
        file_id,
        filename, len(doc_ids),
        f"{len(doc_ids)} sample call transcripts",
        json.dumps(["call transcript", "sample data"]),
        json.dumps({}),
        "2025-12-08T00:00:00Z",
    )

    conn.commit()
    conn.close()
    print(f"  [OK] Registered file '{filename}' ({len(doc_ids)} docs)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print()
    print("========================================")
    print("  Knowledge Mining — Seed Sample Data")
    print("========================================")

    # Validate configuration — only Search is required; Cosmos and SQL are optional
    if not SEARCH_ENDPOINT:
        print("\nERROR: AZURE_SEARCH_ENDPOINT is not set.")
        print("Make sure you have run 'azd up' and a .env file exists in the project root.")
        sys.exit(1)

    # Validate data files exist
    for f in [SEARCH_DATA_FILE, PROCESSED_DATA_FILE, KEY_PHRASES_FILE]:
        if not os.path.exists(f):
            print(f"\nERROR: Data file not found: {f}")
            sys.exit(1)

    # Clear existing data before seeding
    print(f"\n{'='*60}")
    print("Step 0: Clear existing data")
    print(f"{'='*60}")

    # Clear AI Search index (delete + recreate)
    try:
        index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=credential)
        try:
            index_def = index_client.get_index(INDEX_NAME)
            index_client.delete_index(INDEX_NAME)
            print(f"  [OK] Deleted old search index '{INDEX_NAME}'")
        except Exception:
            print(f"  [OK] No existing index '{INDEX_NAME}' to clear")
    except Exception as e:
        print(f"  [WARN] Could not clear search index: {e}")

    # Clear SQL tables
    if SQL_SERVER:
        try:
            import struct
            import pyodbc
            token = credential.get_token("https://database.windows.net/.default")
            token_bytes = token.token.encode("utf-16-le")
            token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
            conn_str = (
                f"Driver={{ODBC Driver 18 for SQL Server}};"
                f"Server={SQL_SERVER};"
                f"Database={SQL_DATABASE};"
                f"Encrypt=yes;TrustServerCertificate=no;"
            )
            conn = pyodbc.connect(conn_str, attrs_before={1256: token_struct})
            cursor = conn.cursor()
            for table in ["documents", "uploaded_files", "filter_schemas", "enrichment_cache"]:
                try:
                    cursor.execute(f"DELETE FROM {table}")
                except Exception:
                    pass  # Table may not exist yet
            conn.commit()
            conn.close()
            print(f"  [OK] Cleared SQL tables")
        except Exception as e:
            print(f"  [WARN] Could not clear SQL: {e}")

    try:
        ensure_search_index()
        upload_search_data()
    except Exception as e:
        print(f"\n  [FAIL] Search upload failed: {e}")
        print("  Make sure your identity has 'Search Index Data Contributor' role.")

    if COSMOS_ENDPOINT:
        try:
            upload_processed_data()
        except Exception as e:
            print(f"\n  [FAIL] Cosmos processed data upload failed: {e}")
            print("  Make sure your identity has Cosmos DB data contributor role.")

        try:
            upload_key_phrases()
        except Exception as e:
            print(f"\n  [FAIL] Cosmos key phrases upload failed: {e}")
            print("  Make sure your identity has Cosmos DB data contributor role.")
    else:
        print("\n  [SKIP] AZURE_COSMOS_ENDPOINT not set — skipping Cosmos DB upload.")

    if SQL_SERVER:
        try:
            upload_to_sql()
            register_uploaded_file()
        except Exception as e:
            print(f"\n  [FAIL] SQL upload failed: {e}")
            print("  Make sure your identity has SQL admin access.")
    else:
        print("\n  [SKIP] No AZURE_SQL_SERVER set — skipping SQL upload.")

    print(f"\n{'='*60}")
    print("  Done!")
    print(f"{'='*60}")
    print(f"  Search Index : {INDEX_NAME}")
    print(f"  Cosmos DB    : {COSMOS_DATABASE}")
    if SQL_SERVER:
        print(f"  Azure SQL    : {SQL_DATABASE}")

    # Notify running API server to refresh its cache
    import urllib.request
    api_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    try:
        req = urllib.request.Request(f"{api_url}/api/ingestion/refresh", method="POST")
        urllib.request.urlopen(req, timeout=5)
        print(f"\n  [OK] API server cache refreshed")
    except Exception:
        print(f"\n  [INFO] Could not reach API at {api_url} — restart the server to pick up new data")
    print()


if __name__ == "__main__":
    main()