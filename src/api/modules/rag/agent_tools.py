"""Tools for RAG agent — AI Search and SQL query capabilities."""

import json
import logging
from typing import Any, Optional

from agent_framework import tool

logger = logging.getLogger(__name__)


@tool
def search_azure_ai_search(query: str, top_k: int = 5, filters: Optional[dict] = None) -> str:
    """Search Azure AI Search index for relevant documents.
    
    This tool searches an Azure AI Search index using hybrid search (keyword + vector).
    Use this when the user asks questions that require searching document content,
    summaries, or specific information from indexed documents.
    
    Args:
        query: The search query to run against the index
        top_k: Maximum number of results to return (default: 5)
        filters: Optional filter criteria as key-value pairs
        
    Returns:
        JSON string containing search results with doc_id, text, summary, type, and source_file
    """
    try:
        from src.api.config import get_settings
        from azure.identity import DefaultAzureCredential
        from azure.search.documents import SearchClient
        from azure.search.documents.models import VectorizedQuery
        
        settings = get_settings()
        if not settings.azure_search_endpoint:
            return json.dumps({
                "success": False,
                "error": "Azure AI Search not configured",
                "results": []
            })
        
        credential = DefaultAzureCredential()
        client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=credential,
        )
        
        # Generate query embedding for vector search
        vector_queries = []
        try:
            from src.api.modules.embeddings.service import EmbeddingsService
            emb_service = EmbeddingsService()
            query_emb = emb_service.generate_embedding(query)
            vector_queries.append(VectorizedQuery(
                vector=query_emb.embedding,
                k_nearest_neighbors=top_k,
                fields="text_vector",
            ))
        except Exception as e:
            logger.debug(f"Vector search unavailable, using keyword only: {e}")
        
        # Use fields that exist in both legacy and chunked index schemas
        select_fields = ["id", "doc_id", "text", "summary", "type", "source_file"]
        
        results = client.search(
            search_text=query,
            vector_queries=vector_queries if vector_queries else None,
            top=top_k,
            select=select_fields,
        )
        
        docs = []
        seen = {}  # doc_id -> index in docs (dedup chunks from same document)
        for r in results:
            doc_id = r.get("doc_id") or r["id"]
            # Strip chunk suffix to get base doc ID
            if "_c" in doc_id:
                doc_id = doc_id.split("_c")[0]
            score = r.get("@search.score", 0)
            if doc_id in seen:
                # Keep the higher-scoring chunk's text
                existing = docs[seen[doc_id]]
                if score > existing["score"]:
                    existing["text"] = r.get("text", "")
                    existing["summary"] = r.get("summary", "")
                    existing["score"] = score
                continue
            seen[doc_id] = len(docs)
            docs.append({
                "doc_id": doc_id,
                "text": r.get("text", ""),
                "summary": r.get("summary", ""),
                "type": r.get("type", "unknown"),
                "source_file": r.get("source_file", ""),
                "score": score,
            })
        
        return json.dumps({
            "success": True,
            "count": len(docs),
            "results": docs
        })
        
    except Exception as e:
        logger.error(f"Azure AI Search tool error: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "results": []
        })


@tool
def get_sql_response(sql_query: str) -> str:
    """Execute a SQL query against the knowledge mining database.
    
    This tool executes SQL queries to fetch structured data from the database.
    Use this when the user asks for:
    - Counts or statistics (e.g., "How many documents?")
    - Specific records matching criteria
    - Aggregations or calculations
    - Structured data that requires SQL queries
    
    The available tables are:
    - documents: id, text_content, summary, source_file, doc_type, metadata
    - Any other configured tables in the knowledge mining database
    
    Args:
        sql_query: Valid T-SQL query to execute
        
    Returns:
        JSON string containing query results or error message
    """
    try:
        from src.api.storage.sql_service import sql_service
        
        sql_service._ensure_init()
        if not sql_service._initialized:
            return json.dumps({
                "success": False,
                "error": "SQL database not available",
                "results": []
            })
        
        conn = sql_service._get_connection()
        cursor = conn.cursor()
        
        # Execute the query
        cursor.execute(sql_query)
        
        # Fetch results
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description] if cursor.description else []
        
        # Convert to list of dicts
        results = []
        for row in rows:
            results.append(dict(zip(columns, row)))
        
        conn.close()
        
        return json.dumps({
            "success": True,
            "count": len(results),
            "columns": columns,
            "results": results
        })
        
    except Exception as e:
        logger.error(f"SQL query tool error: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "results": []
        })
