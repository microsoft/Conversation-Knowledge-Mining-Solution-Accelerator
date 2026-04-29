"""End-to-end test of all Knowledge Mining Platform features."""

import requests
import json
import io
import time
import sys

BASE = "http://127.0.0.1:8000"
HEADERS = {"X-User-Email": "test@example.com", "X-User-Roles": "contributor"}

passed = 0
failed = 0
errors = []


def test(name, fn):
    global passed, failed
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    try:
        fn()
        passed += 1
        print(f"  ✓ PASSED")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  ✗ FAILED: {e}")


# ── 1. Health Check ──
def test_health():
    r = requests.get(f"{BASE}/openapi.json", timeout=10)
    assert r.status_code == 200, f"OpenAPI returned {r.status_code}"
    routes = list(r.json()["paths"].keys())
    print(f"  {len(routes)} API routes available")
    assert len(routes) > 10, f"Expected >10 routes, got {len(routes)}"

test("Health Check & Routes", test_health)


# ── 2. Stats ──
def test_stats():
    r = requests.get(f"{BASE}/api/ingestion/stats", headers=HEADERS, timeout=10)
    assert r.status_code == 200, f"Stats returned {r.status_code}"
    data = r.json()
    total = data.get("total_documents", 0)
    print(f"  Total documents: {total}")
    print(f"  By type: {data.get('by_type', {})}")
    by_dim = data.get("by_dimension", {})
    print(f"  Dimensions: {list(by_dim.keys())}")
    assert total > 0, "No documents found"

test("Document Stats", test_stats)


# ── 3. Files ──
def test_files():
    r = requests.get(f"{BASE}/api/ingestion/files", headers=HEADERS, timeout=10)
    assert r.status_code == 200, f"Files returned {r.status_code}"
    files = r.json()
    print(f"  {len(files)} uploaded files")
    for f in files[:5]:
        fname = f.get("filename", f.get("id", "?"))
        count = f.get("doc_count", "?")
        print(f"    - {fname}: {count} docs")

test("Uploaded Files List", test_files)


# ── 4. Filters ──
def test_filters():
    r = requests.get(f"{BASE}/api/ingestion/filters", headers=HEADERS, timeout=10)
    assert r.status_code == 200, f"Filters returned {r.status_code}"
    data = r.json()
    print(f"  Filter dimensions: {list(data.keys())}")
    for dim, values in data.items():
        print(f"    {dim}: {len(values)} values")

test("Filter Schema", test_filters)


# ── 5. Documents List ──
def test_documents():
    r = requests.get(f"{BASE}/api/ingestion/documents", headers=HEADERS, timeout=10)
    assert r.status_code == 200, f"Documents returned {r.status_code}"
    docs = r.json()
    print(f"  {len(docs)} documents")
    types = set()
    for d in docs:
        t = d.get("type", "unknown")
        types.add(t)
    print(f"  Types: {types}")

test("Documents List", test_documents)


# ── 6. Single Document ──
def test_single_doc():
    # Get first doc ID
    r = requests.get(f"{BASE}/api/ingestion/documents", headers=HEADERS, timeout=10)
    docs = r.json()
    if not docs:
        raise Exception("No documents to test")
    doc_id = docs[0].get("id")
    r = requests.get(f"{BASE}/api/ingestion/documents/{doc_id}", headers=HEADERS, timeout=10)
    assert r.status_code == 200, f"Single doc returned {r.status_code}: {r.text[:200]}"
    doc = r.json()
    print(f"  Document ID: {doc.get('id')}")
    print(f"  Type: {doc.get('type')}")
    print(f"  Text length: {len(doc.get('text', ''))}")

test("Single Document Fetch", test_single_doc)


# ── 7. JSON Upload ──
def test_upload_json():
    test_data = [
        {
            "id": "test-upload-1",
            "type": "support_ticket",
            "text": "Customer called about slow WiFi. We reset the router and it resolved the issue.",
            "metadata": {"product": "ZX-3000", "category": "connectivity"},
        }
    ]
    json_bytes = json.dumps(test_data).encode("utf-8")
    files = {"file": ("test_upload.json", io.BytesIO(json_bytes), "application/json")}
    r = requests.post(f"{BASE}/api/ingestion/upload/json", files=files, headers=HEADERS, timeout=120)
    assert r.status_code == 200, f"Upload returned {r.status_code}: {r.text[:300]}"
    data = r.json()
    print(f"  Loaded: {data.get('total_loaded')} docs")

test("JSON File Upload", test_upload_json)


# ── 8. RAG Chat ──
def test_rag_chat():
    payload = {
        "question": "What are common internet connectivity issues?",
        "top_k": 3,
    }
    r = requests.post(f"{BASE}/api/rag/ask", json=payload, headers=HEADERS, timeout=60)
    assert r.status_code == 200, f"RAG returned {r.status_code}: {r.text[:300]}"
    data = r.json()
    answer = data.get("answer", "")
    sources = data.get("sources", [])
    print(f"  Answer length: {len(answer)}")
    print(f"  Sources: {len(sources)}")
    print(f"  Answer preview: {answer[:150]}...")
    assert len(answer) > 10, "Answer too short"

test("RAG Chat (Ask)", test_rag_chat)


# ── 9. Conversation ──
def test_conversation():
    payload = {
        "messages": [
            {"role": "user", "content": "What products do you have data about?"}
        ],
        "top_k": 3,
    }
    r = requests.post(f"{BASE}/api/rag/conversation", json=payload, headers=HEADERS, timeout=60)
    assert r.status_code == 200, f"Conversation returned {r.status_code}: {r.text[:300]}"
    data = r.json()
    answer = data.get("answer", "")
    print(f"  Answer length: {len(answer)}")
    print(f"  Answer preview: {answer[:150]}...")

test("RAG Conversation", test_conversation)


# ── 10. Chat Sessions (CRUD) ──
def test_chat_sessions():
    # List sessions
    r = requests.get(f"{BASE}/api/rag/chat/sessions", headers=HEADERS, timeout=10)
    assert r.status_code == 200, f"Sessions returned {r.status_code}"
    sessions = r.json()
    print(f"  Existing sessions: {len(sessions)}")

    # Save a session
    save_payload = {
        "session_id": "test-session-1",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help?"},
        ],
    }
    r = requests.post(f"{BASE}/api/rag/chat/save", json=save_payload, headers=HEADERS, timeout=10)
    print(f"  Save status: {r.status_code}")

    # Load the session
    r = requests.get(f"{BASE}/api/rag/chat/load/test-session-1", headers=HEADERS, timeout=10)
    print(f"  Load status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"  Messages loaded: {len(data.get('messages', []))}")

test("Chat Sessions CRUD", test_chat_sessions)


# ── 11. Insights ──
def test_insights():
    r = requests.get(f"{BASE}/api/processing/insights", headers=HEADERS, timeout=120)
    assert r.status_code == 200, f"Insights returned {r.status_code}: {r.text[:300]}"
    data = r.json()
    print(f"  Keys: {list(data.keys())}")
    narrative = data.get("narrative", "")
    print(f"  Narrative: {narrative[:150]}...")
    entities = data.get("entities", [])
    print(f"  Entities: {len(entities)}")

test("Insights Generation", test_insights)


# ── 12. Embeddings ──
def test_embeddings():
    payload = {"text": "How to reset a modem?"}
    r = requests.post(f"{BASE}/api/embeddings/generate", json=payload, headers=HEADERS, timeout=30)
    assert r.status_code == 200, f"Embeddings returned {r.status_code}: {r.text[:200]}"
    data = r.json()
    embedding = data.get("embedding", [])
    print(f"  Embedding dimensions: {len(embedding)}")
    assert len(embedding) > 100, f"Expected >100 dims, got {len(embedding)}"

test("Embedding Generation", test_embeddings)


# ── 13. BYOI External Index ──
def test_byoi_list():
    r = requests.get(f"{BASE}/api/ingestion/external/indexes", headers=HEADERS, timeout=10)
    assert r.status_code == 200, f"BYOI list returned {r.status_code}"
    indexes = r.json()
    print(f"  Connected indexes: {len(indexes)}")

test("BYOI Index List", test_byoi_list)


# ── 14. Delete uploaded test file ──
def test_delete():
    # Find the test upload file
    r = requests.get(f"{BASE}/api/ingestion/files", headers=HEADERS, timeout=10)
    files = r.json()
    test_file = None
    for f in files:
        fname = f.get("filename", f.get("id", ""))
        if "test_upload" in fname:
            test_file = f
            break

    if not test_file:
        print("  No test file to delete (skipping)")
        return

    file_id = test_file.get("id", test_file.get("filename", "").rsplit(".", 1)[0])
    r = requests.delete(f"{BASE}/api/ingestion/files/{file_id}", headers=HEADERS, timeout=30)
    print(f"  Delete status: {r.status_code}")
    assert r.status_code == 200, f"Delete returned {r.status_code}: {r.text[:200]}"

    # Verify
    r = requests.get(f"{BASE}/api/ingestion/stats", headers=HEADERS, timeout=10)
    total = r.json().get("total_documents", 0)
    print(f"  Docs after delete: {total}")

test("File Delete", test_delete)


# ── 15. Pipelines ──
def test_pipelines():
    r = requests.get(f"{BASE}/api/pipelines/capabilities", headers=HEADERS, timeout=10)
    assert r.status_code == 200, f"Capabilities returned {r.status_code}"
    caps = r.json()
    print(f"  Capabilities: {len(caps)}")

    r = requests.get(f"{BASE}/api/pipelines/", headers=HEADERS, timeout=10)
    assert r.status_code == 200, f"Pipelines list returned {r.status_code}"
    pipelines = r.json()
    print(f"  Available pipelines: {len(pipelines)}")
    for p in pipelines[:3]:
        print(f"    - {p.get('name', '?')}")

test("Pipelines", test_pipelines)


# ── Summary ──
print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed+failed}")
print(f"{'='*60}")
if errors:
    print("\nFailed tests:")
    for name, err in errors:
        print(f"  ✗ {name}: {err}")

sys.exit(1 if failed > 0 else 0)
