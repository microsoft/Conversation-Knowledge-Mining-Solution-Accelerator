from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_embedding_deployment: str = "text-embedding-ada-002"
    azure_openai_chat_deployment: str = "gpt-4o"

    # Azure Cognitive Search
    azure_search_endpoint: str = ""
    azure_search_index_name: str = "knowledge-mining-index"

    # Azure Content Understanding
    azure_content_understanding_endpoint: str = ""

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

    # Pipeline
    enable_auto_pipeline_selection: bool = True
    pipeline_default_timeout: int = 30

    # App
    app_env: str = ""
    app_frontend_hostname: str = ""
    data_dir: str = os.path.join(os.path.dirname(__file__), "..", "data")
    pipelines_config_dir: str = os.path.join(os.path.dirname(__file__), "app", "config", "use_cases")

    # External Data Sources
    enable_external_data_sources: bool = True
    external_data_source_default_batch_size: int = 1000
    external_data_source_timeout: int = 60

    # Simple data source config (individual env vars)
    data_source_type: str = ""
    data_source_name: str = ""
    data_source_endpoint: str = ""
    data_source_database: str = ""
    data_source_table: str = ""
    data_source_connection_string: str = ""

    # Advanced: multiple sources as JSON array
    data_sources: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
