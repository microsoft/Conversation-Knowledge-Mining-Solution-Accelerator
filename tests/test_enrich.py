"""Test enrich_batch to check if AI filter generation works."""
import sys
sys.path.insert(0, ".")

from backend.modules.document_intelligence.service import ContentUnderstandingService
cu = ContentUnderstandingService()

test_data = [
    {"id": "test1", "type": "pdf", "text": "This is a housing report about affordability and market trends in 2023.", "metadata": {"source_file": "test.pdf"}},
    {"id": "test2", "type": "pdf", "text": "Construction contract for residential building project.", "metadata": {"source_file": "contract.pdf"}},
]

try:
    result = cu.enrich_batch(test_data)
    print("enrich_batch result keys:", list(result.keys()) if result else "None")
    if result:
        print("domain:", result.get("domain", ""))
        dims = result.get("dimensions", [])
        print(f"dimensions: {len(dims)}")
        for d in dims[:5]:
            vals = d.get("values", [])
            print(f"  - {d.get('id')}: {d.get('label')} ({len(vals)} values)")
            for v in vals[:3]:
                print(f"      {v.get('label')}: {v.get('count', 0)}")
        
        doc_extractions = result.get("doc_extractions", [])
        print(f"doc_extractions: {len(doc_extractions)}")
        for de in doc_extractions[:2]:
            print(f"  summary: {de.get('summary', '')[:80]}")
            print(f"  keywords: {de.get('keywords', [])[:5]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
