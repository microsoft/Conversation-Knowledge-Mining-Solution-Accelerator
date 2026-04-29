"""Base abstraction for external data sources.

To add a new data source type:
1. Create a new file (e.g., snowflake.py) implementing BaseExternalDataSource
2. Add the type to DataSourceType enum below
3. Register it in registry.py's _load_adapters()
4. Add a card to FALLBACK_TYPES in src/app/src/pages/DataSources/DataSources.tsx
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Iterator, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DataSourceType(str, Enum):
    FABRIC = "fabric"
    SQL = "sql"
    SYNAPSE = "synapse"
    ODBC = "odbc"
    AZURE_SEARCH = "azure_search"


class AuthMethod(str, Enum):
    CONNECTION_STRING = "connection_string"
    MANAGED_IDENTITY = "managed_identity"
    ENTRA_ID = "entra_id"


class QueryMode(str, Enum):
    INGEST = "ingest"
    LIVE = "live"
    BOTH = "both"


class FieldMapping(BaseModel):
    """Maps accelerator fields to source columns."""
    id_field: str = "id"
    text_field: str = "text"
    title_field: str = ""
    type_field: str = ""
    timestamp_field: str = ""
    metadata_fields: dict[str, str] = {}  # accelerator_key -> source_column


class DataSourceConfig(BaseModel):
    """Configuration for an external data source connection."""
    id: str = ""
    name: str
    source_type: DataSourceType
    connection_string: str = ""
    endpoint: str = ""
    database: str = ""
    table_or_query: str = ""
    auth_method: AuthMethod = AuthMethod.CONNECTION_STRING
    field_mapping: FieldMapping = FieldMapping()
    query_mode: QueryMode = QueryMode.BOTH
    status: str = "disconnected"  # connected | disconnected | error
    doc_count: int = 0
    last_sync: str = ""
    error_message: str = ""


class ColumnInfo(BaseModel):
    """Schema information for a column in the data source."""
    name: str
    data_type: str
    nullable: bool = True


class BaseExternalDataSource(ABC):
    """Abstract base class for external data source adapters."""

    @abstractmethod
    def connect(self, config: DataSourceConfig) -> bool:
        """Establish connection and validate. Returns True on success."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection."""
        ...

    @abstractmethod
    def test_connection(self, config: DataSourceConfig) -> dict:
        """Test connection without persisting. Returns {success, row_count, message}."""
        ...

    @abstractmethod
    def get_schema(self, config: DataSourceConfig) -> list[ColumnInfo]:
        """Fetch column names and types for the configured table/query."""
        ...

    @abstractmethod
    def search(self, config: DataSourceConfig, query: str, top_k: int = 5,
               filters: Optional[dict] = None) -> list[dict]:
        """Search the data source. Returns normalized documents."""
        ...

    @abstractmethod
    def sample(self, config: DataSourceConfig, count: int = 20) -> list[dict]:
        """Get a sample of rows for preview / insights generation."""
        ...

    @abstractmethod
    def fetch_all(self, config: DataSourceConfig, batch_size: int = 1000) -> Iterator[list[dict]]:
        """Iterate over all rows in batches for Pull & Ingest."""
        ...

    def _apply_field_mapping(self, row: dict, mapping: FieldMapping) -> dict:
        """Transform a source row into accelerator document format."""
        doc = {
            "id": str(row.get(mapping.id_field, "")),
            "text": str(row.get(mapping.text_field, "")),
        }
        if mapping.title_field and mapping.title_field in row:
            doc["title"] = str(row[mapping.title_field])
        if mapping.type_field and mapping.type_field in row:
            doc["type"] = str(row[mapping.type_field])
        else:
            doc["type"] = "external"
        if mapping.timestamp_field and mapping.timestamp_field in row:
            doc["timestamp"] = str(row[mapping.timestamp_field])

        metadata = {}
        for accel_key, src_col in mapping.metadata_fields.items():
            if src_col in row:
                metadata[accel_key] = row[src_col]
        doc["metadata"] = metadata

        return doc
