"""Test script for the data sources module."""

import sys
sys.path.insert(0, ".")

from backend.modules.data_sources.base import (
    DataSourceType, DataSourceConfig, FieldMapping, QueryMode, AuthMethod, ColumnInfo
)
from backend.modules.data_sources.registry import DataSourceRegistry
from backend.modules.data_sources.models import (
    CreateDataSourceRequest, TestConnectionRequest, DataSourceResponse
)


def test_supported_types():
    reg = DataSourceRegistry()
    types = reg.get_supported_types()
    assert len(types) == 5, f"Expected 5 types, got {len(types)}"
    type_ids = [t["source_type"] for t in types]
    assert "fabric" in type_ids
    assert "sql" in type_ids
    assert "synapse" in type_ids
    assert "odbc" in type_ids
    assert "azure_search" in type_ids
    print(f"  Supported types: {', '.join(type_ids)}")


def test_config_creation():
    config = DataSourceConfig(
        name="Test Fabric",
        source_type=DataSourceType.FABRIC,
        endpoint="my-server.database.fabric.microsoft.com",
        database="my-lakehouse",
        table_or_query="conversations",
        auth_method=AuthMethod.MANAGED_IDENTITY,
        field_mapping=FieldMapping(id_field="conv_id", text_field="transcript"),
        query_mode=QueryMode.BOTH,
    )
    assert config.name == "Test Fabric"
    assert config.source_type == DataSourceType.FABRIC
    assert config.field_mapping.id_field == "conv_id"
    assert config.field_mapping.text_field == "transcript"
    assert config.query_mode == QueryMode.BOTH
    print(f"  Config: {config.name} ({config.source_type})")
    print(f"  Mapping: id={config.field_mapping.id_field}, text={config.field_mapping.text_field}")


def test_adapter_lookup():
    reg = DataSourceRegistry()
    for dtype in DataSourceType:
        adapter = reg._get_adapter(dtype)
        print(f"  {dtype.value} -> {adapter.__class__.__name__}")
        assert adapter is not None


def test_field_mapping():
    from backend.modules.data_sources.base import BaseExternalDataSource

    class DummyAdapter(BaseExternalDataSource):
        def connect(self, config): return True
        def disconnect(self): pass
        def test_connection(self, config): return {"success": True}
        def get_schema(self, config): return []
        def search(self, config, query, top_k=5, filters=None): return []
        def sample(self, config, count=20): return []
        def fetch_all(self, config, batch_size=1000): yield []

    adapter = DummyAdapter()
    mapping = FieldMapping(
        id_field="conversation_id",
        text_field="transcript",
        title_field="subject",
        type_field="category",
        metadata_fields={"agent": "agent_name", "duration": "call_duration"},
    )
    row = {
        "conversation_id": "c001",
        "transcript": "Hello, how can I help?",
        "subject": "Billing inquiry",
        "category": "support",
        "agent_name": "Alice",
        "call_duration": "5:30",
        "extra_col": "ignored",
    }
    doc = adapter._apply_field_mapping(row, mapping)
    assert doc["id"] == "c001"
    assert doc["text"] == "Hello, how can I help?"
    assert doc["title"] == "Billing inquiry"
    assert doc["type"] == "support"
    assert doc["metadata"]["agent"] == "Alice"
    assert doc["metadata"]["duration"] == "5:30"
    assert "extra_col" not in doc["metadata"]
    print(f"  Mapped doc: id={doc['id']}, type={doc['type']}, meta_keys={list(doc['metadata'].keys())}")


def test_request_models():
    req = CreateDataSourceRequest(
        name="My SQL DB",
        source_type=DataSourceType.SQL,
        connection_string="Driver={ODBC Driver 18};Server=localhost;Database=test;",
        table_or_query="customer_calls",
        query_mode=QueryMode.INGEST,
    )
    assert req.name == "My SQL DB"
    assert req.source_type == DataSourceType.SQL
    assert req.query_mode == QueryMode.INGEST

    test_req = TestConnectionRequest(
        source_type=DataSourceType.FABRIC,
        endpoint="server.database.fabric.microsoft.com",
        database="lakehouse",
        table_or_query="calls",
    )
    assert test_req.source_type == DataSourceType.FABRIC
    print(f"  CreateRequest: {req.name}")
    print(f"  TestRequest: {test_req.source_type}")


def test_response_model():
    resp = DataSourceResponse(
        id="abc123",
        name="Fabric LH",
        source_type=DataSourceType.FABRIC,
        auth_method=AuthMethod.MANAGED_IDENTITY,
        field_mapping=FieldMapping(),
        query_mode=QueryMode.LIVE,
        status="connected",
        doc_count=5000,
    )
    # Ensure connection_string is NOT in the response model
    resp_dict = resp.model_dump()
    assert "connection_string" not in resp_dict
    assert resp_dict["status"] == "connected"
    print(f"  Response: {resp.name}, status={resp.status}, docs={resp.doc_count}")


def test_in_memory_registry():
    reg = DataSourceRegistry()
    reg._loaded = True  # skip SQL loading

    # Create
    config = DataSourceConfig(
        name="In-Memory Test",
        source_type=DataSourceType.SQL,
        connection_string="not-a-real-connection",
        table_or_query="test_table",
        query_mode=QueryMode.BOTH,
    )
    # Manually add to cache (skip real connection test)
    config.id = "test-001"
    config.status = "connected"
    config.doc_count = 42
    reg._cache[config.id] = config

    # Get
    retrieved = reg.get("test-001")
    assert retrieved is not None
    assert retrieved.name == "In-Memory Test"

    # List
    all_sources = reg.list_all()
    assert len(all_sources) == 1

    # List live
    live = reg.list_live_sources()
    assert len(live) == 1  # query_mode=BOTH includes live

    # Update
    updated = reg.update("test-001", {"name": "Updated Name"})
    assert updated.name == "Updated Name"

    # Delete
    deleted = reg.delete("test-001")
    assert deleted is True
    assert reg.get("test-001") is None
    print(f"  CRUD operations: create, get, list, update, delete all passed")


if __name__ == "__main__":
    tests = [
        ("Supported types", test_supported_types),
        ("Config creation", test_config_creation),
        ("Adapter lookup", test_adapter_lookup),
        ("Field mapping", test_field_mapping),
        ("Request models", test_request_models),
        ("Response model", test_response_model),
        ("In-memory registry CRUD", test_in_memory_registry),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        try:
            print(f"\n[TEST] {name}")
            test_fn()
            print(f"  PASSED")
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if failed > 0:
        sys.exit(1)
