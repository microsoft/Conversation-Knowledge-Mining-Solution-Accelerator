"""FastAPI router for external data source management."""

import logging
from fastapi import APIRouter, HTTPException

from backend.modules.data_sources.base import DataSourceConfig, FieldMapping
from backend.modules.data_sources.models import (
    CreateDataSourceRequest,
    UpdateDataSourceRequest,
    TestConnectionRequest,
    DataSourceResponse,
    TestConnectionResponse,
    IngestResponse,
)
from backend.modules.data_sources.registry import data_source_registry

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_response(config: DataSourceConfig) -> DataSourceResponse:
    return DataSourceResponse(
        id=config.id,
        name=config.name,
        source_type=config.source_type,
        endpoint=config.endpoint,
        database=config.database,
        table_or_query=config.table_or_query,
        auth_method=config.auth_method,
        field_mapping=config.field_mapping,
        query_mode=config.query_mode,
        status=config.status,
        doc_count=config.doc_count,
        last_sync=config.last_sync,
        error_message=config.error_message,
    )


@router.get("/types")
async def get_supported_types():
    """List supported data source types with their config schemas."""
    return data_source_registry.get_supported_types()


@router.get("/")
async def list_data_sources():
    """List all configured data sources."""
    sources = data_source_registry.list_all()
    return [_to_response(s) for s in sources]


@router.post("/")
async def create_data_source(request: CreateDataSourceRequest):
    """Add a new data source connection."""
    config = DataSourceConfig(
        name=request.name,
        source_type=request.source_type,
        connection_string=request.connection_string,
        endpoint=request.endpoint,
        database=request.database,
        table_or_query=request.table_or_query,
        auth_method=request.auth_method,
        field_mapping=request.field_mapping,
        query_mode=request.query_mode,
    )
    result = data_source_registry.create(config)
    return _to_response(result)


@router.get("/{source_id}")
async def get_data_source(source_id: str):
    """Get data source details."""
    config = data_source_registry.get(source_id)
    if not config:
        raise HTTPException(status_code=404, detail="Data source not found")
    return _to_response(config)


@router.put("/{source_id}")
async def update_data_source(source_id: str, request: UpdateDataSourceRequest):
    """Update data source configuration."""
    updates = request.model_dump(exclude_none=True)
    result = data_source_registry.update(source_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Data source not found")
    return _to_response(result)


@router.delete("/{source_id}")
async def delete_data_source(source_id: str):
    """Remove a data source."""
    if not data_source_registry.delete(source_id):
        raise HTTPException(status_code=404, detail="Data source not found")
    return {"success": True}


@router.post("/test")
async def test_connection(request: TestConnectionRequest):
    """Test a data source connection without persisting."""
    config = DataSourceConfig(
        name="test",
        source_type=request.source_type,
        connection_string=request.connection_string,
        endpoint=request.endpoint,
        database=request.database,
        table_or_query=request.table_or_query,
        auth_method=request.auth_method,
    )
    result = data_source_registry.test_connection(config)
    return TestConnectionResponse(**result)


@router.post("/{source_id}/test")
async def test_existing_connection(source_id: str):
    """Test an existing data source connection."""
    config = data_source_registry.get(source_id)
    if not config:
        raise HTTPException(status_code=404, detail="Data source not found")
    result = data_source_registry.test_connection(config)
    return TestConnectionResponse(**result)


@router.get("/{source_id}/schema")
async def get_schema(source_id: str):
    """Fetch column names and types for field mapping."""
    columns = data_source_registry.get_schema(source_id)
    if not columns:
        raise HTTPException(status_code=404, detail="Could not retrieve schema")
    return [c.model_dump() for c in columns]


@router.get("/{source_id}/sample")
async def get_sample(source_id: str, count: int = 10):
    """Preview sample rows from the data source."""
    docs = data_source_registry.sample(source_id, count)
    return docs


@router.post("/{source_id}/ingest")
async def ingest_data(source_id: str):
    """Pull data from the source and ingest into the accelerator."""
    result = data_source_registry.ingest(source_id)
    return IngestResponse(**result)


@router.post("/quick-connect")
async def quick_connect(request: CreateDataSourceRequest):
    """One-shot: test connection, auto-detect fields, create source, return sample.
    Designed for the simplified 'bring your data' wizard."""
    config = DataSourceConfig(
        name=request.name,
        source_type=request.source_type,
        connection_string=request.connection_string,
        endpoint=request.endpoint,
        database=request.database,
        table_or_query=request.table_or_query,
        auth_method=request.auth_method,
        field_mapping=request.field_mapping,
        query_mode=request.query_mode,
    )

    # Test + get schema + auto-detect
    test_result = data_source_registry.test_connection(config)
    if not test_result["success"]:
        return {
            "success": False,
            "message": test_result["message"],
            "source": None,
            "sample": [],
            "suggested_mapping": None,
        }

    # Apply auto-detected mapping if user didn't provide one
    mapping = request.field_mapping
    suggested = test_result.get("suggested_mapping", {})
    if suggested and mapping.text_field == "text" and mapping.id_field == "id":
        # User hasn't customized mapping — use auto-detected
        config.field_mapping = FieldMapping(**suggested)

    # Create the source
    result = data_source_registry.create(config)

    # Get sample with the mapping applied
    sample = data_source_registry.sample(result.id, count=5)

    return {
        "success": True,
        "message": test_result["message"],
        "source": _to_response(result),
        "sample": sample,
        "suggested_mapping": suggested,
        "columns": test_result.get("columns", []),
    }
