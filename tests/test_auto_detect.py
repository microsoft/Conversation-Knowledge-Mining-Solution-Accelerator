"""Test auto-detect field mapping."""
import sys
sys.path.insert(0, ".")

from backend.modules.data_sources.base import ColumnInfo
from backend.modules.data_sources.registry import DataSourceRegistry

reg = DataSourceRegistry()


def test_standard_names():
    cols = [
        ColumnInfo(name="id", data_type="int"),
        ColumnInfo(name="content", data_type="nvarchar"),
        ColumnInfo(name="title", data_type="nvarchar"),
        ColumnInfo(name="category", data_type="nvarchar"),
        ColumnInfo(name="created_at", data_type="datetime2"),
    ]
    m = reg._auto_detect_mapping(cols)
    assert m["id_field"] == "id"
    assert m["text_field"] == "content"
    assert m["title_field"] == "title"
    assert m["type_field"] == "category"
    assert m["timestamp_field"] == "created_at"
    print("  id=id, text=content, title=title, type=category, ts=created_at")


def test_non_obvious_names():
    cols = [
        ColumnInfo(name="record_id", data_type="int"),
        ColumnInfo(name="transcript", data_type="nvarchar"),
        ColumnInfo(name="subject", data_type="nvarchar"),
        ColumnInfo(name="doc_type", data_type="nvarchar"),
        ColumnInfo(name="timestamp", data_type="datetime"),
    ]
    m = reg._auto_detect_mapping(cols)
    assert m["id_field"] == "record_id"
    assert m["text_field"] == "transcript"
    assert m["title_field"] == "subject"
    assert m["type_field"] == "doc_type"
    assert m["timestamp_field"] == "timestamp"
    print("  id=record_id, text=transcript, title=subject, type=doc_type")


def test_unknown_names_fallback():
    cols = [
        ColumnInfo(name="foo", data_type="int"),
        ColumnInfo(name="bar", data_type="str"),
        ColumnInfo(name="baz", data_type="str"),
    ]
    m = reg._auto_detect_mapping(cols)
    assert m["id_field"] == "foo", f"Expected foo, got {m['id_field']}"
    assert m["text_field"] == "bar", f"Expected bar, got {m['text_field']}"
    assert m["title_field"] == ""
    print("  id=foo (first), text=bar (first string), title=(none)")


def test_partial_match():
    cols = [
        ColumnInfo(name="conversation_id", data_type="int"),
        ColumnInfo(name="full_text", data_type="nvarchar"),
        ColumnInfo(name="agent_name", data_type="nvarchar"),
    ]
    m = reg._auto_detect_mapping(cols)
    assert m["text_field"] == "full_text", f"Expected full_text, got {m['text_field']}"
    print("  text=full_text (partial match on 'text')")


def test_quick_connect_router():
    from fastapi.testclient import TestClient
    from backend.modules.data_sources.router import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/api/data-sources")
    client = TestClient(app)

    # quick-connect with a fake DB — should fail gracefully
    resp = client.post("/api/data-sources/quick-connect", json={
        "name": "Test",
        "source_type": "sql",
        "connection_string": "Driver={ODBC Driver 18};Server=fake;Database=test;",
        "table_or_query": "my_table",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data
    assert data["success"] is False  # can't connect to fake
    assert "message" in data
    print(f"  quick-connect returns success={data['success']}, message present")


if __name__ == "__main__":
    tests = [
        ("Standard column names", test_standard_names),
        ("Non-obvious names", test_non_obvious_names),
        ("Unknown names fallback", test_unknown_names_fallback),
        ("Partial match", test_partial_match),
        ("Quick-connect endpoint", test_quick_connect_router),
    ]

    passed = failed = 0
    for name, fn in tests:
        try:
            print(f"\n[TEST] {name}")
            fn()
            print("  PASSED")
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
