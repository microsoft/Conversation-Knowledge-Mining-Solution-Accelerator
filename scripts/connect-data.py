"""Connect an external data source to the Knowledge Mining app.

Registers a data source connection directly in Azure SQL so the app can
query it at runtime. No running backend required — works right after azd up.

Supported sources: Azure AI Search, Microsoft Fabric.

Prerequisites:
  - Run `azd up` first (creates .env with SQL connection details)
  - Your Azure identity must have SQL admin access on the deployed database

Usage:
  python scripts/connect-data.py                          # interactive prompts
  python scripts/connect-data.py --type azure_search \\
      --name "My Index" \\
      --endpoint https://my-search.search.windows.net \\
      --table my-index-name                               # non-interactive
"""

import argparse
import json
import os
import struct
import sys
import uuid

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

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SQL_SERVER = os.getenv("AZURE_SQL_SERVER", "")
SQL_DATABASE = os.getenv("AZURE_SQL_DATABASE", "km-db")

# ---------------------------------------------------------------------------
# Data source types
# ---------------------------------------------------------------------------
SOURCE_TYPES = {
    "1": {
        "type": "azure_search",
        "label": "Azure AI Search",
        "fields": ["endpoint", "table"],
        "prompts": {
            "endpoint": "Search endpoint (e.g. https://my-search.search.windows.net): ",
            "table": "Index name: ",
        },
    },
    "2": {
        "type": "fabric",
        "label": "Microsoft Fabric",
        "fields": ["endpoint", "database", "table"],
        "prompts": {
            "endpoint": "SQL endpoint (e.g. your-server.database.fabric.microsoft.com): ",
            "database": "Lakehouse/Warehouse name: ",
            "table": "Table name: ",
        },
    },
}


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------
def get_sql_connection():
    """Connect to Azure SQL with Entra ID (passwordless)."""
    import pyodbc
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={SQL_SERVER};"
        f"Database={SQL_DATABASE};"
        f"Encrypt=yes;TrustServerCertificate=no;"
    )
    return pyodbc.connect(conn_str, attrs_before={1256: token_struct})


def ensure_table(conn):
    """Create external_data_sources table if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'external_data_sources')
        CREATE TABLE external_data_sources (
            id NVARCHAR(255) PRIMARY KEY,
            name NVARCHAR(500),
            source_type NVARCHAR(50),
            connection_string NVARCHAR(MAX),
            endpoint NVARCHAR(500),
            database_name NVARCHAR(500),
            table_or_query NVARCHAR(MAX),
            auth_method NVARCHAR(50),
            field_mapping NVARCHAR(MAX),
            query_mode NVARCHAR(50),
            status NVARCHAR(50),
            doc_count INT DEFAULT 0,
            last_sync NVARCHAR(100),
            error_message NVARCHAR(MAX),
            created_at DATETIME2 DEFAULT GETUTCDATE(),
            updated_at DATETIME2 DEFAULT GETUTCDATE()
        )
    """)
    conn.commit()


def save_data_source(conn, data: dict):
    """Upsert a data source row into Azure SQL."""
    cursor = conn.cursor()
    cursor.execute("""
        MERGE external_data_sources AS target
        USING (SELECT ? AS id) AS source ON target.id = source.id
        WHEN MATCHED THEN UPDATE SET
            name=?, source_type=?, connection_string=?, endpoint=?,
            database_name=?, table_or_query=?, auth_method=?,
            field_mapping=?, query_mode=?, status=?, doc_count=?,
            last_sync=?, error_message=?, updated_at=GETUTCDATE()
        WHEN NOT MATCHED THEN INSERT
            (id, name, source_type, connection_string, endpoint,
             database_name, table_or_query, auth_method,
             field_mapping, query_mode, status, doc_count,
             last_sync, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """,
        data["id"],
        data["name"], data["source_type"],
        data.get("connection_string", ""), data.get("endpoint", ""),
        data.get("database", ""), data.get("table_or_query", ""),
        data.get("auth_method", "managed_identity"),
        json.dumps(data.get("field_mapping", {})),
        data.get("query_mode", "both"), data.get("status", "disconnected"),
        data.get("doc_count", 0), data.get("last_sync", ""),
        data.get("error_message", ""),
        # INSERT values
        data["id"],
        data["name"], data["source_type"],
        data.get("connection_string", ""), data.get("endpoint", ""),
        data.get("database", ""), data.get("table_or_query", ""),
        data.get("auth_method", "managed_identity"),
        json.dumps(data.get("field_mapping", {})),
        data.get("query_mode", "both"), data.get("status", "disconnected"),
        data.get("doc_count", 0), data.get("last_sync", ""),
        data.get("error_message", ""),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Connection testing (uses the adapter classes directly)
# ---------------------------------------------------------------------------
def test_source_connection(config: dict) -> dict:
    """Test the data source connection using the app's adapter classes."""
    # Add src to path so we can import adapters
    sys.path.insert(0, os.path.join(project_root, "src"))

    from api.modules.data_sources.base import DataSourceConfig, DataSourceType

    adapter_map = {
        "azure_search": "api.modules.data_sources.azure_search",
        "fabric": "api.modules.data_sources.fabric",
    }

    source_type = config["source_type"]
    module_path = adapter_map.get(source_type)
    if not module_path:
        return {"success": False, "row_count": 0, "message": f"Unknown type: {source_type}"}

    import importlib
    mod = importlib.import_module(module_path)
    # Each module has one class that ends with DataSource
    adapter_cls = None
    for attr_name in dir(mod):
        obj = getattr(mod, attr_name)
        if isinstance(obj, type) and attr_name.endswith("DataSource") and attr_name != "BaseExternalDataSource":
            adapter_cls = obj
            break

    if not adapter_cls:
        return {"success": False, "row_count": 0, "message": f"No adapter found for {source_type}"}

    ds_config = DataSourceConfig(
        name=config.get("name", ""),
        source_type=DataSourceType(source_type),
        connection_string=config.get("connection_string", ""),
        endpoint=config.get("endpoint", ""),
        database=config.get("database", ""),
        table_or_query=config.get("table_or_query", ""),
    )

    adapter = adapter_cls()
    return adapter.test_connection(ds_config)


# ---------------------------------------------------------------------------
# Interactive prompts
# ---------------------------------------------------------------------------
def interactive_prompts() -> dict:
    """Gather data source config via interactive prompts."""
    print()
    print("Select a data source type:")
    print()
    for key, info in SOURCE_TYPES.items():
        print(f"  {key}. {info['label']}")
    print()

    choice = input("Enter choice (1-2): ").strip()
    if choice not in SOURCE_TYPES:
        print(f"Invalid choice: {choice}")
        sys.exit(1)

    source = SOURCE_TYPES[choice]
    print(f"\nConfiguring {source['label']}...")
    print()

    name = input("Display name for this data source: ").strip()
    if not name:
        name = source["label"]

    config = {"name": name, "source_type": source["type"]}

    for field in source["fields"]:
        value = input(source["prompts"][field]).strip()
        if field == "table":
            config["table_or_query"] = value
        elif field == "connection_string":
            config["connection_string"] = value
        else:
            config[field] = value

    return config


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Connect a data source to Knowledge Mining")
    parser.add_argument("--type", choices=["azure_search", "fabric"],
                        help="Data source type")
    parser.add_argument("--name", help="Display name")
    parser.add_argument("--endpoint", help="Service endpoint URL")
    parser.add_argument("--database", help="Database/lakehouse name")
    parser.add_argument("--table", help="Table or index name")
    parser.add_argument("--connection-string", help="ODBC connection string")
    args = parser.parse_args()

    print()
    print("========================================")
    print("  Knowledge Mining — Connect Data Source")
    print("========================================")

    # Validate SQL config
    if not SQL_SERVER:
        print("\nERROR: AZURE_SQL_SERVER not set.")
        print("Make sure you have run 'azd up' and a .env file exists.")
        sys.exit(1)

    if args.type:
        config = {
            "name": args.name or args.type,
            "source_type": args.type,
            "endpoint": args.endpoint or "",
            "database": args.database or "",
            "table_or_query": args.table or "",
            "connection_string": args.connection_string or "",
        }
    else:
        config = interactive_prompts()

    print(f"\n  Type    : {config['source_type']}")
    print(f"  Name    : {config['name']}")
    if config.get("endpoint"):
        print(f"  Endpoint: {config['endpoint']}")
    if config.get("table_or_query"):
        print(f"  Table   : {config['table_or_query']}")

    # Step 1: Test connection
    print("\n  Testing connection...")
    try:
        result = test_source_connection(config)
    except Exception as e:
        result = {"success": False, "row_count": 0, "message": str(e)}

    if result["success"]:
        row_count = result.get("row_count", 0)
        print(f"  [OK] Connected — {row_count} rows found")
        config["status"] = "connected"
        config["doc_count"] = row_count
        config["error_message"] = ""
    else:
        print(f"  [FAIL] {result.get('message', 'Connection failed')}")
        retry = input("\n  Register anyway? (y/N): ").strip().lower()
        if retry != "y":
            sys.exit(1)
        config["status"] = "error"
        config["doc_count"] = 0
        config["error_message"] = result.get("message", "")

    # Step 2: Write to Azure SQL
    print(f"\n  Registering in Azure SQL ({SQL_SERVER})...")
    config["id"] = str(uuid.uuid4())[:12]

    try:
        conn = get_sql_connection()
        ensure_table(conn)
        save_data_source(conn, config)
        conn.close()
        print(f"  [OK] Data source '{config['name']}' registered (id: {config['id']})")
    except Exception as e:
        print(f"  [FAIL] SQL write failed: {e}")
        sys.exit(1)

    print(f"\n{'='*40}")
    print("  Done!")
    print(f"{'='*40}")
    print(f"\n  The app will query this source at runtime.")
    print(f"  No data was moved — queries go directly to your source.")
    print()


if __name__ == "__main__":
    main()
