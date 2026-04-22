from backend.capabilities.registry import register


@register("select")
def select(items: list | None = None, where: dict | None = None, limit: int | None = None, sort: str | None = None, context: dict | None = None, **kwargs) -> dict:
    """Select items by condition, with optional limit and sort.

    If items is None, selects from ingested documents and stores IDs in context.
    """
    where = where or {}

    # Default: select from ingested documents
    if items is None:
        from backend.modules.ingestion.service import ingestion_service
        docs = ingestion_service.search_documents(
            doc_type=where.get("type"),
            product=where.get("product"),
            category=where.get("category"),
            query=where.get("query"),
        )
        ids = [d.id for d in docs]
        if limit:
            ids = ids[:limit]
        if context is not None:
            context["filtered_doc_ids"] = ids
        return {"result": ids, "meta": {"count": len(ids)}}

    # Generic: select from any list of dicts
    results = []
    for item in items:
        match = True
        for key, value in where.items():
            item_val = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
            if item_val != value:
                match = False
                break
        if match:
            results.append(item)

    if sort and results:
        results.sort(key=lambda x: x.get(sort, "") if isinstance(x, dict) else getattr(x, sort, ""))
    if limit:
        results = results[:limit]

    return {"result": results, "meta": {"count": len(results)}}
