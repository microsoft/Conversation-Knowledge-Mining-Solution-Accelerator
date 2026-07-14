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
import shutil
import subprocess
import struct
import sys
import uuid
from urllib import request as urlrequest
from urllib.parse import urlparse

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


def _run_az_command(args: list[str]) -> tuple[int, str, str]:
    """Run an Azure CLI/AZD command and return rc/stdout/stderr."""
    if not args:
        return 1, "", "No command provided"

    exe = args[0]
    resolved = shutil.which(exe)

    # Windows can expose Azure CLIs via .cmd files and/or well-known install paths.
    if not resolved and os.name == "nt":
        for ext in (".cmd", ".exe", ".bat"):
            resolved = shutil.which(f"{exe}{ext}")
            if resolved:
                break

    if not resolved and os.name == "nt":
        win_candidates = {
            "az": [
                r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
                r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
            ],
            "azd": [
                os.path.expandvars(r"%USERPROFILE%\\.azd\\bin\\azd.exe"),
                r"C:\Program Files\Azure Developer CLI\azd.exe",
            ],
        }
        for candidate in win_candidates.get(exe, []):
            if candidate and os.path.exists(candidate):
                resolved = candidate
                break

    if not resolved:
        return 127, "", f"Command not found: {exe}"

    cmd = [resolved, *args[1:]]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = proc.communicate()
        return proc.returncode, (stdout or "").strip(), (stderr or "").strip()
    except OSError as e:
        return 1, "", str(e)


def get_azd_env_value(name: str) -> str:
    """Read a value from the active azd environment, if available."""
    rc, out, _ = _run_az_command(["azd", "env", "get-value", name])
    if rc != 0:
        return ""
    return "" if out.startswith("ERROR:") else out


def get_api_principal_context() -> tuple[str, str]:
    """Resolve backend API principal ID and app name from env/azd/Azure."""
    principal_id = (os.getenv("AZURE_API_PRINCIPAL_ID") or "").strip()
    api_app_name = (os.getenv("API_APP_NAME") or "").strip()

    if not principal_id:
        principal_id = get_azd_env_value("AZURE_API_PRINCIPAL_ID")
    if not api_app_name:
        api_app_name = get_azd_env_value("API_APP_NAME")

    if not api_app_name:
        backend_uri = (os.getenv("SERVICE_BACKEND_URI") or get_azd_env_value("SERVICE_BACKEND_URI")).strip()
        parsed = urlparse(backend_uri)
        host = parsed.hostname or ""
        if host.endswith(".azurewebsites.net"):
            api_app_name = host.split(".")[0]

    if not principal_id and api_app_name:
        env_name = (os.getenv("AZURE_ENV_NAME") or get_azd_env_value("AZURE_ENV_NAME")).strip()
        resource_group = (os.getenv("AZURE_RESOURCE_GROUP") or "").strip()
        if not resource_group and env_name:
            resource_group = f"rg-{env_name}"
        if resource_group:
            rc, out, _ = _run_az_command(
                [
                    "az",
                    "webapp",
                    "identity",
                    "show",
                    "--name",
                    api_app_name,
                    "--resource-group",
                    resource_group,
                    "--query",
                    "principalId",
                    "-o",
                    "tsv",
                ]
            )
            if rc == 0:
                principal_id = out

    return principal_id.strip(), api_app_name.strip()


def get_search_service_resource_id(endpoint: str) -> str:
    """Resolve the Azure resource ID for an Azure AI Search endpoint."""
    endpoint = normalize_endpoint(endpoint)
    host = urlparse(endpoint).hostname or ""
    if not host.endswith(".search.windows.net"):
        return ""

    service_name = host.split(".")[0]
    if not service_name:
        return ""

    rc, out, _ = _run_az_command(
        [
            "az",
            "resource",
            "list",
            "--name",
            service_name,
            "--resource-type",
            "Microsoft.Search/searchServices",
            "--query",
            "[0].id",
            "-o",
            "tsv",
        ]
    )
    if rc != 0:
        return ""
    return out.strip()


def ensure_search_index_reader_role(endpoint: str) -> None:
    """Grant API managed identity Search Index Data Reader on external search service."""
    principal_id, app_name = get_api_principal_context()
    if not principal_id:
        print("  [WARN] Could not resolve API managed identity principal ID; skipping Search RBAC assignment.")
        return

    scope = get_search_service_resource_id(endpoint)
    if not scope:
        print("  [WARN] Could not resolve Azure AI Search resource ID from endpoint; skipping Search RBAC assignment.")
        return

    role_name = "Search Index Data Reader"
    rc, existing, _ = _run_az_command(
        [
            "az",
            "role",
            "assignment",
            "list",
            "--assignee-object-id",
            principal_id,
            "--scope",
            scope,
            "--role",
            role_name,
            "--query",
            "[0].id",
            "-o",
            "tsv",
        ]
    )
    if rc == 0 and existing:
        identity_label = f"{app_name} ({principal_id})" if app_name else principal_id
        print(f"  [OK] RBAC already exists: {role_name} on external search for {identity_label}")
        return

    rc, _, err = _run_az_command(
        [
            "az",
            "role",
            "assignment",
            "create",
            "--assignee-object-id",
            principal_id,
            "--assignee-principal-type",
            "ServicePrincipal",
            "--scope",
            scope,
            "--role",
            role_name,
        ]
    )
    if rc == 0:
        identity_label = f"{app_name} ({principal_id})" if app_name else principal_id
        print(f"  [OK] Granted {role_name} on external search to {identity_label}")
        return

    print(f"  [WARN] Failed to grant {role_name} role automatically: {err}")


def normalize_endpoint(endpoint: str) -> str:
    """Return an https endpoint without trailing slash."""
    endpoint = (endpoint or "").strip()
    if not endpoint:
        return endpoint
    if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
        endpoint = f"https://{endpoint}"
    return endpoint.rstrip("/")


def list_azure_search_indexes(endpoint: str) -> list[str]:
    """List index names from an Azure AI Search service using Entra auth."""
    endpoint = normalize_endpoint(endpoint)
    if not endpoint:
        return []

    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    token = credential.get_token("https://search.azure.com/.default")
    req = urlrequest.Request(
        f"{endpoint}/indexes?api-version=2024-07-01",
        headers={
            "Authorization": f"Bearer {token.token}",
            "Accept": "application/json",
        },
        method="GET",
    )

    with urlrequest.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
        values = payload.get("value", []) if isinstance(payload, dict) else []
        return [item.get("name") for item in values if isinstance(item, dict) and item.get("name")]


def resolve_azure_search_index(config: dict, interactive: bool) -> dict:
    """Ensure Azure AI Search config has index name; discover indexes when missing."""
    if config.get("source_type") != "azure_search":
        return config

    config["endpoint"] = normalize_endpoint(config.get("endpoint", ""))
    current_index = (config.get("table_or_query") or "").strip()
    if current_index:
        config["table_or_query"] = current_index
        return config

    try:
        indexes = list_azure_search_indexes(config.get("endpoint", ""))
    except Exception as e:
        if interactive:
            print(f"\n  Could not auto-discover indexes: {e}")
            manual = input("  Enter index name manually: ").strip()
            config["table_or_query"] = manual
            return config
        raise RuntimeError(
            "Index name is required for Azure AI Search. Auto-discovery failed; pass --table <index-name>."
        ) from e

    if not indexes:
        if interactive:
            manual = input("\n  No indexes found. Enter index name manually: ").strip()
            config["table_or_query"] = manual
            return config
        raise RuntimeError(
            "No indexes were found on this Azure AI Search endpoint. "
            "Confirm the endpoint is correct, then pass --table <index-name> if it exists."
        )

    if len(indexes) == 1:
        config["table_or_query"] = indexes[0]
        print(f"\n  Auto-selected index: {indexes[0]}")
        return config

    if interactive:
        print("\n  Available indexes:")
        for i, idx in enumerate(indexes, start=1):
            print(f"    {i}. {idx}")
        while True:
            choice = input(f"  Select index (1-{len(indexes)}): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(indexes):
                config["table_or_query"] = indexes[int(choice) - 1]
                return config
            print("  Invalid selection.")

    raise RuntimeError(
        "Multiple indexes found. Pass --table <index-name> or run without CLI args for interactive selection."
    )


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
    # Add repo root to path so imports using `src.*` resolve consistently.
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from src.api.modules.data_sources.base import DataSourceConfig, DataSourceType

    adapter_map = {
        "azure_search": "src.api.modules.data_sources.azure_search",
        "fabric": "src.api.modules.data_sources.fabric",
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
        # For Azure AI Search, index can be auto-discovered from endpoint.
        if source["type"] == "azure_search" and field == "table":
            value = input("Index name (optional, press Enter to auto-discover): ").strip()
        else:
            value = input(source["prompts"][field]).strip()
        if field == "table":
            config["table_or_query"] = value
        elif field == "connection_string":
            config["connection_string"] = value
        else:
            config[field] = value

    return config


def prompt_missing_fields(config: dict) -> dict:
    """When --type is provided but required values are missing, prompt for them."""
    source_type = (config.get("source_type") or "").strip()

    if source_type == "azure_search":
        if not (config.get("endpoint") or "").strip():
            config["endpoint"] = normalize_endpoint(
                input("Search endpoint (e.g. https://my-search.search.windows.net): ").strip()
            )
        if not (config.get("table_or_query") or "").strip():
            config["table_or_query"] = input("Index name (optional, press Enter to auto-discover): ").strip()

    elif source_type == "fabric":
        if not (config.get("endpoint") or "").strip():
            config["endpoint"] = input("SQL endpoint (e.g. your-server.database.fabric.microsoft.com): ").strip()
        if not (config.get("database") or "").strip():
            config["database"] = input("Lakehouse/Warehouse name: ").strip()
        if not (config.get("table_or_query") or "").strip():
            config["table_or_query"] = input("Table name: ").strip()

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

    # Interactive when user did not pass --type, OR when --type was passed
    # without all required values and the terminal can accept prompts.
    is_interactive = not bool(args.type)
    if args.type and sys.stdin.isatty():
        if args.type == "azure_search":
            is_interactive = is_interactive or not (args.endpoint and args.table)
        elif args.type == "fabric":
            is_interactive = is_interactive or not (args.endpoint and args.database and args.table)

    if args.type:
        config = {
            "name": args.name or args.type,
            "source_type": args.type,
            "endpoint": normalize_endpoint(args.endpoint or ""),
            "database": args.database or "",
            "table_or_query": args.table or "",
            "connection_string": args.connection_string or "",
        }
        if is_interactive:
            config = prompt_missing_fields(config)
    else:
        config = interactive_prompts()

    try:
        config = resolve_azure_search_index(config, interactive=is_interactive)
    except Exception as e:
        print(f"\n  [FAIL] {e}")
        sys.exit(1)

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

    if config.get("source_type") == "azure_search":
        print("\n  Assigning API app access to external Azure AI Search...")
        ensure_search_index_reader_role(config.get("endpoint", ""))

    # Step 3: Notify the running backend so it reloads the data source into memory.
    # This makes the source visible in the UI immediately without restarting the API.
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    try:
        import urllib.request as _urlreq
        payload = json.dumps({
            "name": config["name"],
            "source_type": config["source_type"],
            "endpoint": config.get("endpoint", ""),
            "database": config.get("database", ""),
            "table_or_query": config.get("table_or_query", ""),
            "auth_method": "managed_identity",
            "query_mode": "live",
        }).encode()
        req = _urlreq.Request(
            f"{backend_url}/api/data-sources/",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        admin_key = os.getenv("ADMIN_API_KEY", "")
        if admin_key:
            req.add_header("X-Admin-Api-Key", admin_key)
        with _urlreq.urlopen(req, timeout=5) as resp:
            if resp.status in (200, 201):
                print(f"  [OK] Backend notified — source is live in the app")
    except Exception as e:
        print(f"  [INFO] Could not notify backend ({e}) — source will appear after backend restart")

    print(f"\n{'='*40}")
    print("  Done!")
    print(f"{'='*40}")
    print(f"\n  The app will query this source at runtime.")
    print(f"  No data was moved — queries go directly to your source.")
    print()

    # Write connection details to a temp file so the calling PowerShell script
    # can read the actual index/table name after interactive prompts.
    last_conn_path = os.path.join(project_root, ".last_byod_connection.json")
    try:
        last_conn = {
            "source_type": config.get("source_type", ""),
            "source_id": config.get("id", ""),
            "name": config.get("name", ""),
            "table_or_query": config.get("table_or_query", ""),
            "endpoint": config.get("endpoint", ""),
        }
        with open(last_conn_path, "w") as _f:
            json.dump(last_conn, _f)
    except Exception:
        pass


if __name__ == "__main__":
    main()
