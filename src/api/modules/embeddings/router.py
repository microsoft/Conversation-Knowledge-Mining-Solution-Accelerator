from fastapi import APIRouter, Depends, HTTPException

from src.api.modules.embeddings.service import embeddings_service
from src.api.modules.embeddings.models import (
    EmbeddingRequest,
    EmbeddingResponse,
    IndexDocumentRequest,
    IndexResult,
    SearchRequest,
    SearchResult,
)
from src.api.modules.security.auth import get_current_user, require_role
from src.api.modules.security.models import User

router = APIRouter()


@router.post("/generate", response_model=EmbeddingResponse)
async def generate_embedding(
    request: EmbeddingRequest,
    user: User = Depends(get_current_user),
):
    """Generate an embedding for a text string."""
    try:
        return embeddings_service.generate_embedding(request.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {e}")


@router.post("/index", response_model=IndexResult)
async def index_documents(
    request: IndexDocumentRequest = IndexDocumentRequest(),
    user: User = Depends(require_role("contributor")),
):
    """Index ingested documents into the vector store."""
    doc_ids = [request.doc_id] if request.doc_id else None
    try:
        return embeddings_service.index_documents(doc_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")


@router.post("/search", response_model=list[SearchResult])
async def vector_search(
    request: SearchRequest,
    user: User = Depends(get_current_user),
):
    """Perform vector similarity search."""
    try:
        return embeddings_service.search(query=request.query, top_k=request.top_k, filters=request.filters)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@router.get("/stats")
async def vector_store_stats(user: User = Depends(get_current_user)):
    return {"total_vectors": embeddings_service.store_size}


@router.delete("/clear")
async def clear_index(user: User = Depends(require_role("admin"))):
    embeddings_service.clear()
    return {"message": "Vector store cleared"}
