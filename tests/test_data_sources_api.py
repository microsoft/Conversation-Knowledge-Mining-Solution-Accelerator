"""Test the FastAPI router endpoints for data sources."""

import sys
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from backend.modules.data_sources.router import router
from fastapi import FastAPI

app = FastAPI()
app.include_router(router, prefix="/api/data-sources")

client = TestClient(app)


def test_get_types():
    resp = client.get("/api/data-sources/types")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
    type_ids = [t["source_type"] for t in data]
    assert "fabric" in type_ids
    assert "sql" in type_ids
    print(f"  GET /types -> {len(data)} types")


def test_list_empty():
    resp = client.get("/api/data-sources/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    print(f"  GET / -> {len(data)} sources")


def test_create_source():
    resp = client.post("/api/data-sources/", json={
        "name": "Test SQL Source",
        "source_type": "sql",
        "connection_string": "Driver={ODBC Driver 18};Server=fake;Database=test;",
        "table_or_query": "my_table",
        "query_mode": "both",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test SQL Source"
    assert data["source_type"] == "sql"
    assert "id" in data
    # Status should be 'error' since connection won't work locally
    assert data["status"] in ("connected", "error")
    # Connection string should NOT be in the response
    assert "connection_string" not in data
    print(f"  POST / -> created id={data['id']}, status={data['status']}")
    return data["id"]


def test_get_source(source_id):
    resp = client.get(f"/api/data-sources/{source_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == source_id
    assert data["name"] == "Test SQL Source"
    print(f"  GET /{source_id} -> {data['name']}")


def test_list_sources():
    resp = client.get("/api/data-sources/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    print(f"  GET / -> {len(data)} sources")


def test_update_source(source_id):
    resp = client.put(f"/api/data-sources/{source_id}", json={
        "name": "Updated Source Name",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Source Name"
    print(f"  PUT /{source_id} -> name updated to '{data['name']}'")


def test_delete_source(source_id):
    resp = client.delete(f"/api/data-sources/{source_id}")
    assert resp.status_code == 200
    # Verify deleted
    resp2 = client.get(f"/api/data-sources/{source_id}")
    assert resp2.status_code == 404
    print(f"  DELETE /{source_id} -> deleted successfully")


def test_404():
    resp = client.get("/api/data-sources/nonexistent")
    assert resp.status_code == 404
    print(f"  GET /nonexistent -> 404 as expected")


def test_test_connection():
    resp = client.post("/api/data-sources/test", json={
        "source_type": "sql",
        "connection_string": "Driver={ODBC Driver 18};Server=fake;Database=test;",
        "table_or_query": "my_table",
    })
    assert resp.status_code == 200
    data = resp.json()
    # Will fail since no real DB but should return properly
    assert "success" in data
    assert "message" in data
    print(f"  POST /test -> success={data['success']}")


if __name__ == "__main__":
    tests = [
        ("GET /types", lambda: test_get_types()),
        ("GET / (empty)", lambda: test_list_empty()),
        ("Test connection", lambda: test_test_connection()),
    ]

    # CRUD flow tests
    source_id = None
    crud_tests = [
        ("POST / (create)", lambda: test_create_source()),
    ]

    passed = 0
    failed = 0

    for name, fn in tests:
        try:
            print(f"\n[TEST] {name}")
            fn()
            print(f"  PASSED")
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1

    # CRUD
    try:
        print(f"\n[TEST] CRUD flow")
        source_id = test_create_source()
        test_get_source(source_id)
        test_list_sources()
        test_update_source(source_id)
        test_delete_source(source_id)
        test_404()
        print(f"  PASSED")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed} tests")
    if failed > 0:
        sys.exit(1)
