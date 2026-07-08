from pydantic_settings import BaseSettings
from functools import lru_cache
import logging
import os

logger = logging.getLogger(__name__)

_CONFIG_DIR = os.path.dirname(__file__)
_REPO_ROOT_ENV = os.path.abspath(os.path.join(_CONFIG_DIR, "..", "..", ".env"))
_LOCAL_ENV = os.path.join(_CONFIG_DIR, ".env")


class Settings(BaseSettings):
    # Azure AI Foundry Agent — single pre-created chat agent (created by a separate script).
    # The agent owns its system prompt/model; backend only references it by name.
    azure_ai_agent_endpoint: str = ""  # AZURE_AI_AGENT_ENDPOINT
    agent_name_chat: str = ""          # AGENT_NAME_CHAT
    agent_name_title: str = ""         # AGENT_NAME_TITLE
    # Whether the chat agent was created with the SQL tool (scenario-dependent).
    # The backend only attaches get_sql_response when this is true.
    use_sql: bool = False              # USE_SQL

    # Azure AI Foundry (Foundry IQ) — preferred path for centralized model governance
    azure_foundry_endpoint: str = ""  # e.g., https://<project>.services.ai.azure.com

    # Azure OpenAI (direct SDK fallback when Foundry IQ is not configured)
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_embedding_deployment: str = "text-embedding-ada-002"
    azure_openai_chat_deployment: str = "gpt-5.1"

    # Azure Cognitive Search
    azure_search_endpoint: str = ""
    azure_search_index_name: str = "knowledge-mining-index"

    # Azure Content Understanding
    azure_content_understanding_endpoint: str = ""
    azure_content_understanding_api_version: str = "2024-12-01-preview"
    azure_content_understanding_analyzer_id: str = "km-document"

    # Admin API Key (local dev / script auth — never set in production)
    admin_api_key: str = ""

    # Microsoft Entra ID (AAD)
    azure_ad_tenant_id: str = ""
    azure_ad_client_id: str = ""

    # RAG Configuration
    rag_top_k: int = 5
    rag_enable_reranking: bool = False

    # Storage
    document_store_type: str = "memory"
    vector_store_type: str = "memory"
    pipeline_store_type: str = "memory"

    # Azure Storage
    azure_storage_account: str = ""
    azure_storage_container: str = "documents"

    # Azure Cosmos DB (optional )
    azure_cosmos_endpoint: str = ""
    azure_cosmos_database: str = "km-db"

    # Azure SQL (primary database for all storage)
    azure_sql_server: str = ""
    azure_sql_database: str = "km-db"

    # Database provider: "sql" (default) or "cosmos"
    database_provider: str = "sql"

    # Pipeline
    enable_auto_pipeline_selection: bool = True
    pipeline_default_timeout: int = 30

    # App
    app_env: str = ""
    app_frontend_hostname: str = ""
    startup_strict_in_prod: bool = True
    auth_allow_anonymous_in_prod: bool = False
    data_dir: str = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    pipelines_config_dir: str = os.path.join(os.path.dirname(__file__), "app", "config", "use_cases")

    # Limits
    max_upload_file_size_mb: int = 100
    max_json_documents_per_upload: int = 10000
    max_concurrent_uploads: int = 10

    # Timeouts
    llm_request_timeout_sec: int = 60
    sql_connection_timeout_sec: int = 30
    queue_poll_interval_sec: int = 5
    cu_poll_max_wait_sec: int = 1200  # 20 min cap for large/complex scanned PDFs
    cu_poll_base_wait_sec: int = 60
    cu_poll_per_mb_wait_sec: int = 60  # 1 min per MB (scanned PDFs are slow)
    cu_use_sas_url: bool = True  # Prefer SAS URL to avoid CU byte re-upload overhead
    processing_stale_timeout_minutes: int = 20

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # External Data Sources
    enable_external_data_sources: bool = True
    external_data_source_default_batch_size: int = 1000
    external_data_source_timeout: int = 60

    model_config = {
        "env_file": (_REPO_ROOT_ENV, _LOCAL_ENV, ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def validate_startup(self) -> list[str]:
        """Check for missing configuration and return warnings.

        This does NOT block startup — the app can run locally without Azure
        services. But it logs which features will be unavailable.
        """
        warnings = []
        if not self.azure_foundry_endpoint and not self.azure_openai_endpoint:
            warnings.append("No LLM endpoint configured (azure_foundry_endpoint or azure_openai_endpoint). Chat and insights will not work.")
        if not self.azure_search_endpoint:
            warnings.append("azure_search_endpoint not set. Hybrid search will not work.")
        if not self.azure_content_understanding_endpoint:
            warnings.append("azure_content_understanding_endpoint not set. Document extraction will not work.")
        if not self.azure_sql_server and self.database_provider == "sql":
            warnings.append("azure_sql_server not set. Data will only persist in memory.")
        if not self.azure_cosmos_endpoint and self.database_provider == "cosmos":
            warnings.append("azure_cosmos_endpoint not set but database_provider is 'cosmos'. Chat and insights will not persist.")
        if not self.azure_storage_account:
            warnings.append("azure_storage_account not set. Async queue processing disabled; uploads will process in-process.")
        return warnings

    def validate_production_requirements(self) -> list[str]:
        """Return blocking configuration errors for production deployments."""
        errors: list[str] = []

        if not self.app_frontend_hostname:
            errors.append("app_frontend_hostname is required in production.")

        if not self.azure_foundry_endpoint and not self.azure_openai_endpoint:
            errors.append("One LLM endpoint is required in production: azure_foundry_endpoint or azure_openai_endpoint.")

        if not self.azure_search_endpoint:
            errors.append("azure_search_endpoint is required in production.")

        if not self.azure_content_understanding_endpoint:
            errors.append("azure_content_understanding_endpoint is required in production.")

        if self.database_provider == "sql" and not self.azure_sql_server:
            errors.append("azure_sql_server is required in production when database_provider is 'sql'.")

        if self.database_provider == "cosmos" and not self.azure_cosmos_endpoint:
            errors.append("azure_cosmos_endpoint is required in production when database_provider is 'cosmos'.")

        if not self.azure_storage_account:
            errors.append("azure_storage_account is required in production.")

        return errors


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    for w in settings.validate_startup():
        logger.warning(f"[CONFIG] {w}")

    is_prod = settings.app_env.lower() in ("prod", "production")
    if is_prod and settings.startup_strict_in_prod:
        blocking = settings.validate_production_requirements()
        if blocking:
            joined = " | ".join(blocking)
            logger.error(f"[CONFIG] Production validation failed: {joined}")
            raise RuntimeError(f"Production configuration validation failed: {joined}")

    return settings
