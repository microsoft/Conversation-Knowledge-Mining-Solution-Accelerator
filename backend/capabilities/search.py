from backend.capabilities.registry import register
from backend.capabilities.embed import embed
from backend.storage.vector_store import vector_store


@register("search")
def search(query: str = "", top_k: int = 5, filters: dict | None = None, context: dict | None = None, **kwargs) -> dict:
    """Embed query and search vector store."""
    emb_result = embed(query)
    results = vector_store.search(emb_result["result"], top_k=top_k, filters=filters)
    return {"result": results, "meta": {"total": len(results), "top_k": top_k}}
