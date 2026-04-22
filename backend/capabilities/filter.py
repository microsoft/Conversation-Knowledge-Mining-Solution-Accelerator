from backend.capabilities.registry import register


@register("filter")
def filter_items(items: list | None = None, condition: dict | None = None, context: dict | None = None, **kwargs) -> dict:
    """Lightweight non-AI filter. Works on any list of dicts by metadata matching.

    If items is None, filters ingested documents and stores IDs in context.
    condition: {"field": "value"} pairs to match against item metadata.
    """
    condition = condition or {}

    # Default: filter ingested documents
    if items is None:
        from backend.modules.ingestion.service import ingestion_service
        docs = ingestion_service.search_documents(
            doc_type=condition.get("type"),
            product=condition.get("product"),
            category=condition.get("category"),
            query=condition.get("query"),
        )
        if context is not None:
            context["filtered_doc_ids"] = [d.id for d in docs]
        return {"filtered_count": len(docs)}

    # Generic: filter any list of dicts
    results = []
    for item in items:
        match = True
        for key, value in condition.items():
            item_val = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
            if item_val != value:
                match = False
                break
        if match:
            results.append(item)
    return {"filtered": results, "filtered_count": len(results)}
