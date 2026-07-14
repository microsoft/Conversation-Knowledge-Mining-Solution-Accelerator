#!/usr/bin/env python3
"""
BYOD Data Enrichment Service

Enriches external data sources (Azure AI Search, Fabric) by:
1. Retrieving documents from the external source
2. Running them through Content Understanding / LLM extraction
3. Extracting: topics, summaries, key phrases, entities
4. Storing enriched metadata back to source
5. Regenerating insights with enriched data

Usage:
    python enrich_byod_data.py --source-id "my-search-index" --source-type azure_search
    python enrich_byod_data.py --source-id "my-workspace-connection" --source-type fabric --batch-size 20
"""

import argparse
import json
import logging
import os
import sys
from typing import List, Dict, Any
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.config import get_settings
from src.api.modules.processing.service import processing_service
from src.api.modules.ingestion.external_index import external_index_service
from src.api.modules.data_sources.registry import data_source_registry
from src.api.storage.sql_service import sql_service

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class ByodEnrichmentService:
    """Enriches BYOD data sources with topics, summaries, entities, and key phrases."""

    def __init__(self):
        self.processing_service = processing_service
        self.settings = get_settings()
        self.enriched_count = 0
        self.error_count = 0

    def enrich_azure_search_source(self, index_id: str, batch_size: int = 10) -> Dict[str, Any]:
        """Enrich documents in an Azure AI Search external index."""
        logger.info(f"Starting enrichment for Azure AI Search index: {index_id}")
        
        # Try to get from external_index_service (in-memory cache)
        index = external_index_service.get(index_id)
        
        # If not found in cache, try to retrieve from data_source_registry (SQL)
        if not index:
            try:
                from src.api.modules.data_sources.registry import data_source_registry
                from src.api.modules.data_sources.base import DataSourceType
                
                # Look through all registered data sources for a matching Azure Search index
                data_source_registry._ensure_loaded()
                for config in data_source_registry.list_all():
                    if (config.source_type == DataSourceType.AZURE_SEARCH and 
                        (config.id == index_id or config.table_or_query == index_id)):
                        logger.info(f"Found Azure Search data source in registry: {config.id}")
                        
                        # Get the adapter and retrieve documents
                        adapter = data_source_registry._get_adapter(config.source_type)
                        documents = adapter.search(config, query="", top_k=10000) or []
                        logger.info(f"Retrieved {len(documents)} documents from index {config.table_or_query}")
                        
                        # Enrich in batches
                        enriched_docs = []
                        for i, doc in enumerate(documents):
                            try:
                                enriched = self._enrich_document(doc)
                                enriched_docs.append(enriched)
                                self.enriched_count += 1
                                
                                if (i + 1) % batch_size == 0:
                                    logger.info(f"Enriched {i + 1}/{len(documents)} documents")
                                        
                            except Exception as e:
                                logger.error(f"Error enriching document {doc.get('doc_id', 'unknown')}: {e}")
                                self.error_count += 1
                        
                        self._store_enriched_metadata(enriched_docs, "azure_search")
                        
                        logger.info(f"Enrichment complete: {self.enriched_count} success, {self.error_count} errors")
                        return {
                            "success": True,
                            "source_id": config.id,
                            "source_type": "azure_search",
                            "documents_processed": len(documents),
                            "enriched": self.enriched_count,
                            "errors": self.error_count,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                
                # No matching data source found
                logger.error(f"Azure Search index/data source not found: {index_id}")
                return {"success": False, "error": f"Azure Search index '{index_id}' not found in registry", "enriched": 0}
                
            except Exception as e:
                logger.error(f"Error accessing data source registry: {e}")
                return {"success": False, "error": f"Failed to load data source: {str(e)}", "enriched": 0}
        
        # Use index from external_index_service if found
        documents = self._get_azure_search_documents(index)
        logger.info(f"Retrieved {len(documents)} documents from index {index.index_name}")
        
        # Enrich in batches
        enriched_docs = []
        for i, doc in enumerate(documents):
            try:
                enriched = self._enrich_document(doc)
                enriched_docs.append(enriched)
                self.enriched_count += 1
                
                if (i + 1) % batch_size == 0:
                    logger.info(f"Enriched {i + 1}/{len(documents)} documents")
                    
            except Exception as e:
                logger.error(f"Error enriching document {doc.get('id', 'unknown')}: {e}")
                self.error_count += 1
        
        # Store enriched metadata back to index (via SQL for now, can be extended to direct index updates)
        self._store_enriched_metadata(enriched_docs, "azure_search")
        
        logger.info(f"Enrichment complete: {self.enriched_count} success, {self.error_count} errors")
        return {
            "success": True,
            "source_id": index_id,
            "source_type": "azure_search",
            "documents_processed": len(documents),
            "enriched": self.enriched_count,
            "errors": self.error_count,
            "timestamp": datetime.utcnow().isoformat()
        }

    def enrich_fabric_source(self, source_id: str, batch_size: int = 10) -> Dict[str, Any]:
        """Enrich documents in a Fabric data source."""
        logger.info(f"Starting enrichment for Fabric source: {source_id}")
        
        # Get the data source configuration from registry
        config = data_source_registry.get(source_id)
        if not config:
            logger.error(f"Fabric source config not found: {source_id}")
            return {"success": False, "error": "Source not found", "enriched": 0}
        
        # Get data source adapter
        from src.api.modules.data_sources.base import DataSourceType
        if config.source_type != DataSourceType.FABRIC:
            logger.error(f"Source is not a Fabric type: {config.source_type}")
            return {"success": False, "error": "Invalid source type", "enriched": 0}
        
        adapter = data_source_registry._get_adapter(config.source_type)
        
        # Get all documents from Fabric table
        documents = self._get_fabric_documents(adapter, config)
        logger.info(f"Retrieved {len(documents)} documents from Fabric table {config.table_or_query}")
        
        # Enrich in batches
        enriched_docs = []
        for i, doc in enumerate(documents):
            try:
                enriched = self._enrich_document(doc)
                enriched_docs.append(enriched)
                self.enriched_count += 1
                
                if (i + 1) % batch_size == 0:
                    logger.info(f"Enriched {i + 1}/{len(documents)} documents")
                    
            except Exception as e:
                logger.error(f"Error enriching document {doc.get('id', 'unknown')}: {e}")
                self.error_count += 1
        
        # Store enriched metadata (via SQL for now)
        self._store_enriched_metadata(enriched_docs, "fabric")
        
        logger.info(f"Enrichment complete: {self.enriched_count} success, {self.error_count} errors")
        return {
            "success": True,
            "source_id": source_id,
            "source_type": "fabric",
            "documents_processed": len(documents),
            "enriched": self.enriched_count,
            "errors": self.error_count,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _get_azure_search_documents(self, index) -> List[Dict[str, Any]]:
        """Retrieve all documents from Azure AI Search index."""
        try:
            from azure.search.documents import SearchClient
            from azure.identity import DefaultAzureCredential
            
            client = SearchClient(
                endpoint=index.endpoint,
                index_name=index.index_name,
                credential=DefaultAzureCredential(),
            )
            
            # Search for all documents
            results = client.search(search_text="*", top=10000)
            
            documents = []
            for result in results:
                doc = {
                    "id": result.get("id", f"doc_{len(documents)}"),
                    "text": result.get(index.text_field, ""),
                    "title": result.get(index.title_field, ""),
                }
                # Include metadata fields
                for field in index.metadata_fields:
                    if field in result:
                        doc[field] = result[field]
                documents.append(doc)
            
            return documents
        except Exception as e:
            logger.error(f"Failed to get documents from Azure Search: {e}")
            return []

    def _get_fabric_documents(self, adapter, config) -> List[Dict[str, Any]]:
        """Retrieve all documents from Fabric table."""
        try:
            # Get all rows from the configured text field
            documents = adapter.search(config, query="", top_k=10000)
            return documents
        except Exception as e:
            logger.error(f"Failed to get documents from Fabric: {e}")
            return []

    def _enrich_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Extract enrichment metadata for a single document."""
        text = doc.get("text", "")
        if not text or len(text.strip()) < 10:
            # Skip very short documents
            return doc
        
        enrichment = {
            "id": doc.get("id"),
            "text": text,
            "title": doc.get("title", ""),
        }
        
        try:
            # Extract summary
            summary_response = self.processing_service.summarize(text, max_length=150)
            enrichment["summary"] = summary_response.summary
            logger.debug(f"Summary for {doc.get('id')}: {summary_response.summary[:50]}...")
        except Exception as e:
            logger.warning(f"Failed to generate summary: {e}")
            enrichment["summary"] = ""
        
        try:
            # Extract entities
            entities_response = self.processing_service.extract_entities(text)
            enrichment["entities"] = [ent.model_dump() for ent in entities_response.entities]
            logger.debug(f"Extracted {len(enrichment['entities'])} entities for {doc.get('id')}")
        except Exception as e:
            logger.warning(f"Failed to extract entities: {e}")
            enrichment["entities"] = []
        
        try:
            # Extract topics and key phrases using simple LLM approach
            topic_response = self._extract_topic_and_phrases(text)
            enrichment["topic"] = topic_response.get("topic", "")
            enrichment["key_phrases"] = topic_response.get("key_phrases", [])
            logger.debug(f"Topic for {doc.get('id')}: {enrichment['topic']}")
        except Exception as e:
            logger.warning(f"Failed to extract topics/phrases: {e}")
            enrichment["topic"] = ""
            enrichment["key_phrases"] = []
        
        # Preserve original metadata
        for key in doc:
            if key not in enrichment:
                enrichment[key] = doc[key]
        
        return enrichment

    def _extract_topic_and_phrases(self, text: str) -> Dict[str, Any]:
        """Extract primary topic and key phrases from text using LLM."""
        try:
            from src.api.capabilities._llm import get_llm_client
            
            client = get_llm_client()
            response = client.chat.completions.create(
                model=self.settings.azure_openai_chat_deployment,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract the primary topic (in 6 words or less) and top 5-10 key phrases from the text. "
                            "Return ONLY a JSON object with 'topic' (string) and 'key_phrases' (array of strings). "
                            "No other text."
                        ),
                    },
                    {"role": "user", "content": text[:2000]},  # Limit text length
                ],
                temperature=0.1,
                max_completion_tokens=300,
            )
            
            raw = response.choices[0].message.content.strip()
            from src.api.utils.constants import strip_code_fences
            raw = strip_code_fences(raw)
            
            result = json.loads(raw)
            return {
                "topic": result.get("topic", ""),
                "key_phrases": result.get("key_phrases", [])
            }
        except Exception as e:
            logger.error(f"Failed to extract topic/phrases: {e}")
            return {"topic": "", "key_phrases": []}

    def _store_enriched_metadata(self, enriched_docs: List[Dict[str, Any]], source_type: str):
        """Store enriched metadata in SQL database."""
        try:
            sql_service._ensure_init()
            if not sql_service.available:
                logger.warning("SQL service not available, skipping metadata storage")
                return
            
            conn = sql_service._get_connection()
            cursor = conn.cursor()
            
            for doc in enriched_docs:
                try:
                    doc_id = doc.get("id", "")
                    summary = doc.get("summary", "")
                    entities = json.dumps(doc.get("entities", []))
                    key_phrases = json.dumps(doc.get("key_phrases", []))
                    topic = doc.get("topic", "")
                    source_file = doc.get("title", "")
                    
                    # Insert or update document with enrichment
                    cursor.execute("""
                        MERGE INTO documents AS target
                        USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)) AS source (
                            id, source_type, summary, entities, key_phrases, topics, 
                            source_file, text_content, doc_type
                        )
                        ON target.id = source.id
                        WHEN MATCHED THEN
                            UPDATE SET 
                                summary = source.summary,
                                entities = source.entities,
                                key_phrases = source.key_phrases,
                                topics = source.topics,
                                source_file = source.source_file
                        WHEN NOT MATCHED THEN
                            INSERT (id, source_type, summary, entities, key_phrases, topics, 
                                    source_file, text_content, doc_type)
                            VALUES (source.id, source.source_type, source.summary, source.entities, 
                                    source.key_phrases, source.topics, source.source_file, 
                                    source.text_content, source.doc_type);
                    """, (
                        doc_id, source_type, summary, entities, key_phrases, topic,
                        source_file, doc.get("text", ""), "byod"
                    ))
                    
                except Exception as e:
                    logger.error(f"Error storing enrichment for {doc.get('id')}: {e}")
            
            conn.commit()
            conn.close()
            logger.info(f"Stored enrichment metadata for {len(enriched_docs)} documents")
            
        except Exception as e:
            logger.error(f"Failed to store enriched metadata: {e}")


def main():
    parser = argparse.ArgumentParser(description="Enrich BYOD data sources")
    parser.add_argument("--source-id", required=True, help="Source ID (index name or connection ID)")
    parser.add_argument(
        "--source-type",
        required=True,
        choices=["azure_search", "fabric"],
        help="Type of external data source"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Batch size for logging progress"
    )
    parser.add_argument(
        "--enriched-only",
        action="store_true",
        help="Only process documents that are not already enriched (currently accepted for compatibility)",
    )
    
    args = parser.parse_args()
    
    logger.info(f"Starting BYOD enrichment: source_type={args.source_type}, source_id={args.source_id}")
    
    service = ByodEnrichmentService()
    
    try:
        if args.source_type == "azure_search":
            result = service.enrich_azure_search_source(args.source_id, args.batch_size)
        elif args.source_type == "fabric":
            result = service.enrich_fabric_source(args.source_id, args.batch_size)
        else:
            logger.error(f"Unknown source type: {args.source_type}")
            return 1
        
        logger.info(f"Enrichment result: {json.dumps(result, indent=2)}")
        
        # Print result for PowerShell to parse
        print(json.dumps(result))
        
        return 0 if result.get("success") else 1
        
    except Exception as e:
        logger.error(f"Enrichment failed with error: {e}", exc_info=True)
        error_result = {
            "success": False,
            "error": str(e),
            "enriched": 0,
            "timestamp": datetime.utcnow().isoformat()
        }
        print(json.dumps(error_result))
        return 1


if __name__ == "__main__":
    sys.exit(main())
