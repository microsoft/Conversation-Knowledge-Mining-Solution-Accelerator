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
                k=top_k,
                fields="text_vector",
            ))
        except Exception as e:
            logger.debug(f"Vector search unavailable, using keyword only: {e}")
        
        # Schema-agnostic search avoids brittle $select failures across different index schemas.
        results = list(client.search(
            search_text=query,
            vector_queries=vector_queries if vector_queries else None,
            top=top_k,
        ))
        
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
                "text": r.get("text") or r.get("content") or r.get("summary") or r.get("title") or "",
                "summary": r.get("summary", ""),
                "type": r.get("type", "unknown"),
                "source_file": r.get("source_file") or r.get("title") or "",
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
    """Execute a T-SQL query against the knowledge mining documents table.

    TABLE: documents
    COLUMNS (always available):
      id            - document identifier
      text_content  - full conversation/document text
      summary       - AI-generated summary
      source_file   - filename the record came from
      doc_type      - file extension / type
      metadata      - JSON column; use JSON_VALUE(metadata, '$.field') to filter

    METADATA FIELDS (call get_schema_and_sample_values first if unsure of exact values):
      JSON_VALUE(metadata, '$.region')          - geographic region
      JSON_VALUE(metadata, '$.priority')        - priority level
      JSON_VALUE(metadata, '$.status')          - current status
      JSON_VALUE(metadata, '$.claim_type')      - type of claim or topic
      JSON_VALUE(metadata, '$.fraud_signal')    - fraud signal flag
      JSON_VALUE(metadata, '$.channel')         - interaction channel
      JSON_VALUE(metadata, '$.policy_type')     - policy or product type
      JSON_VALUE(metadata, '$.adjuster_team')   - team responsible
      JSON_VALUE(metadata, '$.estimated_amount_usd') - monetary estimate

    CRITICAL RULES:
    - All metadata values are stored as strings — always compare with single-quoted strings
    - Match values EXACTLY as stored (case-sensitive). Call get_schema_and_sample_values
      first to discover exact values before filtering on metadata fields.
    - NEVER guess metadata values. If uncertain, run a discovery query first:
        SELECT DISTINCT JSON_VALUE(metadata, '$.field') FROM documents
    - Use TOP N to limit large result sets (e.g., SELECT TOP 10 ...)
    - For text search use: text_content LIKE '%keyword%'

    Args:
        sql_query: Valid T-SQL query to execute against the documents table

    Returns:
        JSON string with results, column names, and row count
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
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description] if cursor.description else []
        results = [dict(zip(columns, row)) for row in rows]
        conn.close()

        return json.dumps({
            "success": True,
            "count": len(results),
            "columns": columns,
            "results": results,
            "hint": "If count is 0, call get_schema_and_sample_values to verify exact field values before retrying."
        }, default=str)

    except Exception as e:
        logger.error(f"SQL query tool error: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "results": [],
            "hint": "Check your SQL syntax and field names. Use get_schema_and_sample_values to verify schema."
        })


@tool
def get_schema_and_sample_values(top_n: int = 5) -> str:
    """Discover the exact metadata field names and sample values stored in the documents table.

    Call this BEFORE writing SQL queries with metadata filters, especially when:
    - A previous query returned zero rows
    - You are unsure of exact field names or value casing
    - The user references a concept that could map to multiple field names

    Args:
        top_n: Number of distinct sample values to return per field (default: 5)

    Returns:
        JSON with field names, sample values, and total document count
    """
    try:
        from src.api.storage.sql_service import sql_service

        sql_service._ensure_init()
        if not sql_service._initialized:
            return json.dumps({"success": False, "error": "SQL database not available"})

        conn = sql_service._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM documents")
        total = cursor.fetchone()[0]

        cursor.execute(
            "SELECT TOP 20 metadata FROM documents "
            "WHERE metadata IS NOT NULL AND LEN(metadata) > 2"
        )
        field_samples: dict[str, set] = {}
        for row in cursor.fetchall():
            try:
                meta = json.loads(row[0])
                if not isinstance(meta, dict):
                    continue
                for key, val in meta.items():
                    if val is None:
                        continue
                    sv = str(val).strip()
                    if sv:
                        field_samples.setdefault(key, set()).add(sv)
            except Exception:
                continue

        schema = {
            "total_documents": total,
            "metadata_fields": {
                field: sorted(list(values))[:top_n]
                for field, values in sorted(field_samples.items())
            }
        }
        conn.close()

        return json.dumps({"success": True, "schema": schema}, default=str)

    except Exception as e:
        logger.error(f"Schema discovery tool error: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)})
