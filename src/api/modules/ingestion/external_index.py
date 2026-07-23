"""Service for managing external Azure AI Search index connections.

Allows users to bring their own pre-indexed data and chat with it / generate insights
without uploading files through the app.
"""

import logging
from typing import Optional
from pydantic import BaseModel

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient

logger = logging.getLogger(__name__)


class ExternalIndex(BaseModel):
    """An external Azure AI Search index connection."""
    id: str
    name: str  # Display name
    endpoint: str  # Azure AI Search endpoint URL
    index_name: str  # Index name
    text_field: str = "content"  # Field containing searchable text
    title_field: str = ""  # Optional title/filename field
    metadata_fields: list[str] = []  # Additional fields to retrieve
    doc_count: int = 0
    connected: bool = False


class ConnectIndexRequest(BaseModel):
    name: str
    endpoint: str
    index_name: str
    text_field: str = "content"
    title_field: str = ""
    metadata_fields: list[str] = []


class ExternalIndexService:
    """Manages connections to external Azure AI Search indexes."""

    def __init__(self):
        self._indexes: dict[str, ExternalIndex] = {}
        self._credential = DefaultAzureCredential()

    def connect(self, request: ConnectIndexRequest) -> ExternalIndex:
        """Validate and connect to an external index."""
        index_id = f"{request.index_name}@{request.endpoint.split('//')[1].split('.')[0]}"

        # Validate connection by fetching doc count
        try:
            client = SearchClient(
                endpoint=request.endpoint,
                index_name=request.index_name,
                credential=self._credential,
            )
            count = client.get_document_count()

            index = ExternalIndex(
                id=index_id,
                name=request.name,
                endpoint=request.endpoint,
                index_name=request.index_name,
                text_field=request.text_field,
                title_field=request.title_field,
                metadata_fields=request.metadata_fields,
                doc_count=count,
                connected=True,
            )
            self._indexes[index_id] = index
            logger.info(f"Connected to external index: {request.index_name} ({count} docs)")
            return index
        except Exception as e:
            logger.warning(f"Failed to connect to index {request.index_name}: {e}")
            raise ValueError(f"Could not connect to index: {e}")

    def disconnect(self, index_id: str) -> bool:
        if index_id in self._indexes:
            del self._indexes[index_id]
            return True
        return False

    def get(self, index_id: str) -> Optional[ExternalIndex]:
        return self._indexes.get(index_id)

    def list_all(self) -> list[ExternalIndex]:
        return list(self._indexes.values())

    def search(self, index_id: str, query: str, top_k: int = 5) -> list[dict]:
        """Search an external index and return results."""
        index = self._indexes.get(index_id)
        if not index or not index.connected:
            return []

        try:
            client = SearchClient(
                endpoint=index.endpoint,
                index_name=index.index_name,
                credential=self._credential,
            )

            # Build select fields
            select = [index.text_field]
            if index.title_field:
                select.append(index.title_field)
            select.extend(index.metadata_fields)

            results = client.search(
                search_text=query,
                top=top_k,
                select=select,
            )

            docs = []
            for r in results:
                doc = {
                    "doc_id": r.get("id", r.get(index.title_field, f"doc_{len(docs)}")),
                    "text": r.get(index.text_field, ""),
                    "score": r.get("@search.score", 0),
                    "source_file": r.get(index.title_field, ""),
                    "type": "external",
                }
                # Include metadata fields
                for field in index.metadata_fields:
                    if field in r:
                        doc[field] = r[field]
                docs.append(doc)

            return docs
        except Exception as e:
            logger.warning(f"External index search failed: {e}")
            return []

    def sample_documents(self, index_id: str, sample_size: int = 20) -> list[dict]:
        """Get a sample of documents for insights generation."""
        index = self._indexes.get(index_id)
        if not index:
            return []

        try:
            client = SearchClient(
                endpoint=index.endpoint,
                index_name=index.index_name,
                credential=self._credential,
            )

            select = [index.text_field]
            if index.title_field:
                select.append(index.title_field)
            select.extend(index.metadata_fields)

            results = client.search(
                search_text="*",
                top=sample_size,
                select=select,
            )

            docs = []
            for r in results:
                text = r.get(index.text_field, "")
                docs.append({
                    "id": r.get("id", f"ext_{len(docs)}"),
                    "text": text[:500],
                    "title": r.get(index.title_field, ""),
                })
            return docs
        except Exception as e:
            logger.warning(f"Failed to sample external index: {e}")
            return []


external_index_service = ExternalIndexService()
