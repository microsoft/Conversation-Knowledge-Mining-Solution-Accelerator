from typing import Optional

import numpy as np
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from src.api.config import get_settings
from src.api.modules.embeddings.models import EmbeddingResponse, IndexResult, SearchResult
from src.api.modules.ingestion.service import ingestion_service


class EmbeddingsService:
    """Generate embeddings via Azure OpenAI and manage a local vector store."""

    def __init__(self):
        self._vector_store: dict[str, dict] = {}
        self._client: Optional[AzureOpenAI] = None

    def _get_client(self) -> AzureOpenAI:
        if self._client is None:
            settings = get_settings()
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
            self._client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version="2024-10-21",
            )
        return self._client

    def generate_embedding(self, text: str) -> EmbeddingResponse:
        settings = get_settings()
        client = self._get_client()
        response = client.embeddings.create(
            input=text,
            model=settings.azure_openai_embedding_deployment,
        )
        embedding = response.data[0].embedding
        return EmbeddingResponse(
            text=text[:200],
            embedding=embedding,
            model=settings.azure_openai_embedding_deployment,
            dimensions=len(embedding),
        )

    def index_documents(self, doc_ids: Optional[list[str]] = None) -> IndexResult:
        """Generate embeddings for ingested documents and store locally."""
        errors: list[str] = []
        indexed = 0

        docs = ingestion_service.documents
        if doc_ids:
            docs = {k: v for k, v in docs.items() if k in doc_ids}

        for doc_id, doc in docs.items():
            try:
                text = ingestion_service.normalize_text(doc)
                if not text.strip():
                    continue
                emb = self.generate_embedding(text)
                self._vector_store[doc_id] = {
                    "embedding": emb.embedding,
                    "text": text,
                    "metadata": {
                        "doc_id": doc_id,
                        "type": doc.type,
                        "product": doc.metadata.product,
                        "category": doc.metadata.category,
                    },
                }
                indexed += 1
            except Exception as e:
                errors.append(f"{doc_id}: {str(e)}")

        return IndexResult(indexed_count=indexed, index_name="local_vector_store", errors=errors)

    def search(self, query: str, top_k: int = 5, filters: Optional[dict] = None,
               document_ids: Optional[list[str]] = None) -> list[SearchResult]:
        """Perform vector similarity search, optionally scoped to specific documents."""
        query_emb = self.generate_embedding(query)
        query_vec = np.array(query_emb.embedding)

        scores: list[tuple[str, float]] = []
        for chunk_id, entry in self._vector_store.items():
            # Scope filtering: only include specified documents
            if document_ids is not None:
                entry_doc_id = entry["metadata"].get("doc_id", chunk_id)
                if entry_doc_id not in document_ids:
                    continue

            if filters:
                skip = False
                for key, value in filters.items():
                    if entry["metadata"].get(key) != value:
                        skip = True
                        break
                if skip:
                    continue

            doc_vec = np.array(entry["embedding"])
            similarity = float(
                np.dot(query_vec, doc_vec)
                / (np.linalg.norm(query_vec) * np.linalg.norm(doc_vec) + 1e-10)
            )
            scores.append((chunk_id, similarity))

        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for doc_id, score in scores[:top_k]:
            entry = self._vector_store[doc_id]
            results.append(SearchResult(
                doc_id=doc_id,
                score=round(score, 4),
                text=entry["text"],
                metadata=entry["metadata"],
            ))
        return results

    @property
    def store_size(self) -> int:
        return len(self._vector_store)

    def clear(self):
        self._vector_store.clear()


embeddings_service = EmbeddingsService()
