from typing import Optional
import numpy as np
from src.api.storage.base import BaseVectorStore


class InMemoryVectorStore(BaseVectorStore):
    def __init__(self):
        self._store: dict[str, dict] = {}

    def upsert(self, id: str, embedding: list[float], text: str, metadata: dict) -> None:
        self._store[id] = {"embedding": embedding, "text": text, "metadata": metadata}

    def search(self, query_embedding: list[float], top_k: int = 5, filters: Optional[dict] = None) -> list[dict]:
        query_vec = np.array(query_embedding)
        scores: list[tuple[str, float]] = []
        for chunk_id, entry in self._store.items():
            if filters:
                if any(entry["metadata"].get(k) != v for k, v in filters.items()):
                    continue
            doc_vec = np.array(entry["embedding"])
            sim = float(np.dot(query_vec, doc_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(doc_vec) + 1e-10))
            scores.append((chunk_id, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [
            {"id": cid, "score": round(s, 4), "text": self._store[cid]["text"][:500], "metadata": self._store[cid]["metadata"]}
            for cid, s in scores[:top_k]
        ]

    def count(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()


vector_store = InMemoryVectorStore()
