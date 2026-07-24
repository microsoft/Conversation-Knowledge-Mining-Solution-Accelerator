"""Pydantic models for data source API requests/responses."""

from typing import Optional
from pydantic import BaseModel

from src.api.modules.data_sources.base import (
    DataSourceType,
    AuthMethod,
    QueryMode,
    FieldMapping,
    ColumnInfo,
)


class CreateDataSourceRequest(BaseModel):
    name: str
    source_type: DataSourceType
    use_case: str = ""  # Optional: which use case does this data belong to?
    connection_string: str = ""
    endpoint: str = ""
    database: str = ""
    table_or_query: str = ""
    auth_method: AuthMethod = AuthMethod.CONNECTION_STRING
    field_mapping: FieldMapping = FieldMapping()
    query_mode: QueryMode = QueryMode.BOTH


class RegisterScenarioRequest(BaseModel):
    """Register a seeded scenario as an inert 'native' data source."""
    name: str
    use_case: str = ""
    doc_count: int = 0


class UpdateDataSourceRequest(BaseModel):
    name: Optional[str] = None
    use_case: Optional[str] = None
    connection_string: Optional[str] = None
    endpoint: Optional[str] = None
    database: Optional[str] = None
    table_or_query: Optional[str] = None
    auth_method: Optional[AuthMethod] = None
    field_mapping: Optional[FieldMapping] = None
    query_mode: Optional[QueryMode] = None


class TestConnectionRequest(BaseModel):
    source_type: DataSourceType
    connection_string: str = ""
    endpoint: str = ""
    database: str = ""
    table_or_query: str = ""
    auth_method: AuthMethod = AuthMethod.CONNECTION_STRING


class DataSourceResponse(BaseModel):
    id: str
    name: str
    source_type: DataSourceType
    display_name: str  # User-friendly label (e.g., "Azure AI Search" instead of "azure_search")
    use_case: str = ""  # Use case name (e.g., "Contact Center", "Mortgage Application")
    endpoint: str = ""
    database: str = ""
    table_or_query: str = ""
    auth_method: AuthMethod
    field_mapping: FieldMapping
    query_mode: QueryMode
    status: str
    doc_count: int = 0
    last_sync: str = ""
    error_message: str = ""
    # Never expose connection_string in responses


class TestConnectionResponse(BaseModel):
    success: bool
    row_count: int = 0
    message: str = ""
    columns: list[ColumnInfo] = []
    suggested_mapping: Optional[dict] = None


class DataSourceTypeInfo(BaseModel):
    source_type: DataSourceType
    label: str
    description: str
    requires_connection_string: bool
    requires_endpoint: bool
    supports_live_query: bool


class IngestResponse(BaseModel):
    success: bool
    total_ingested: int = 0
    message: str = ""
