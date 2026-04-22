from typing import Optional
from backend.storage.base import BaseDocumentStore
from backend.models.knowledge_object import KnowledgeObject


class InMemoryDocumentStore(BaseDocumentStore):
    def __init__(self):
        self._store: dict[str, KnowledgeObject] = {}

    def put(self, obj: KnowledgeObject) -> None:
        self._store[obj.id] = obj

    def get(self, id: str) -> Optional[KnowledgeObject]:
        return self._store.get(id)

    def list_all(self) -> list[KnowledgeObject]:
        return list(self._store.values())

    def query(self, **filters) -> list[KnowledgeObject]:
        results = self.list_all()
        if filters.get("type"):
            results = [r for r in results if r.type == filters["type"]]
        if filters.get("product"):
            results = [r for r in results if r.metadata.get("product") == filters["product"]]
        if filters.get("category"):
            results = [r for r in results if r.metadata.get("category") == filters["category"]]
        if filters.get("text_query"):
            q = filters["text_query"].lower()
            results = [r for r in results if q in r.content.lower()]
        return results

    def clear(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


document_store = InMemoryDocumentStore()
