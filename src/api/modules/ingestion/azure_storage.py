"""Service for persisting documents to Azure Blob Storage and indexing in Azure AI Search."""

import json
import logging
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
)

from src.api.config import get_settings

logger = logging.getLogger(__name__)


class AzureStorageService:
    """Uploads documents to Azure Blob Storage and indexes them in Azure AI Search."""

    def __init__(self):
        self._blob_client: Optional[BlobServiceClient] = None
        self._search_client: Optional[SearchClient] = None
        self._credential = None

    def _get_credential(self):
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        return self._credential

    def _get_blob_client(self) -> BlobServiceClient:
        if self._blob_client is None:
            settings = get_settings()
            url = f"https://{settings.azure_storage_account}.blob.core.windows.net"
            self._blob_client = BlobServiceClient(
                account_url=url, credential=self._get_credential()
            )
        return self._blob_client

    def _get_search_client(self) -> SearchClient:
        if self._search_client is None:
            settings = get_settings()
            self._search_client = SearchClient(
                endpoint=settings.azure_search_endpoint,
                index_name=settings.azure_search_index_name,
                credential=self._get_credential(),
            )
        return self._search_client

    def _ensure_search_index(self):
        """Create the search index if it doesn't exist."""
        settings = get_settings()
        index_client = SearchIndexClient(
            endpoint=settings.azure_search_endpoint,
            credential=self._get_credential(),
        )
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
            SearchableField(name="text", type=SearchFieldDataType.String),
            SearchableField(name="summary", type=SearchFieldDataType.String),
            SimpleField(name="type", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="product", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="timestamp", type=SearchFieldDataType.String, filterable=True, sortable=True),
            SimpleField(name="source_file", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="key_phrases", type=SearchFieldDataType.String, collection=True, filterable=True),
            SearchableField(name="entities", type=SearchFieldDataType.String, collection=True, filterable=True),
            SearchableField(name="topics", type=SearchFieldDataType.String, collection=True, filterable=True),
        ]
        index = SearchIndex(name=settings.azure_search_index_name, fields=fields)
        try:
            index_client.create_or_update_index(index)
        except Exception as e:
            logger.warning(f"Could not ensure search index: {e}")

    def upload_to_blob(self, doc_id: str, doc_data: dict) -> bool:
        """Upload a single document to blob storage."""
        settings = get_settings()
        try:
            blob_service = self._get_blob_client()
            container = blob_service.get_container_client(settings.azure_storage_container)

            # Create container if needed
            if not container.exists():
                container.create_container()

            blob = container.get_blob_client(f"{doc_id}.json")
            blob.upload_blob(
                json.dumps(doc_data, indent=2),
                overwrite=True,
                content_settings=ContentSettings(content_type="application/json"),
            )
            return True
        except Exception as e:
            logger.debug(f"Blob upload failed for {doc_id}: {e}")
            return False

    def index_in_search(self, documents: list[dict]) -> int:
        """Index documents in Azure AI Search. Returns count of successfully indexed docs."""
        if not documents:
            return 0

        self._ensure_search_index()
        search_client = self._get_search_client()

        indexed = 0
        try:
            result = search_client.upload_documents(documents=documents)
            for r in result:
                if r.succeeded:
                    indexed += 1
                else:
                    logger.warning(f"Search index failed for {r.key}: {r.error_message}")
        except Exception as e:
            logger.warning(f"Search indexing failed: {e}")

        return indexed

    def persist_documents(self, docs: list[dict]) -> dict:
        """Upload docs to blob storage and index in search. Called after ingestion.

        Args:
            docs: List of raw document dicts with id, type, text, metadata keys.

        Returns:
            Summary dict with blob_uploaded and search_indexed counts.
        """
        blob_count = 0
        blob_failed = 0
        search_docs = []

        for doc in docs:
            # Upload to blob
            if self.upload_to_blob(doc["id"], doc):
                blob_count += 1
            else:
                blob_failed += 1

            # Prepare for search indexing
            text = doc.get("text", "")
            if isinstance(text, list):
                text = "\n".join(
                    f"{seg.get('speaker', 'Unknown')}: {seg.get('text', '')}"
                    for seg in text
                )

            search_docs.append({
                "id": doc["id"],
                "text": text,
                "summary": doc.get("summary", ""),
                "type": doc.get("type", "unknown"),
                "product": doc.get("metadata", {}).get("product", ""),
                "category": doc.get("metadata", {}).get("category", ""),
                "timestamp": doc.get("metadata", {}).get("timestamp", ""),
                "source_file": doc.get("metadata", {}).get("source_file", ""),
                "key_phrases": doc.get("key_phrases", []),
                "entities": [e.get("name", "") for e in doc.get("entities", []) if isinstance(e, dict)],
                "topics": doc.get("topics", []),
            })

        if blob_failed > 0:
            logger.warning(f"Blob upload: {blob_failed}/{len(docs)} failed (auth issue — assign 'Storage Blob Data Contributor')")

        # Index in search
        search_count = self.index_in_search(search_docs)

        logger.info(f"Persisted {blob_count} to blob, {search_count} to search index")
        return {"blob_uploaded": blob_count, "search_indexed": search_count}


azure_storage_service = AzureStorageService()
