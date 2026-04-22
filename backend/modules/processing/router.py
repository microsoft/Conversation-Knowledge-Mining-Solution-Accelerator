from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.modules.processing.service import processing_service
from backend.modules.processing.models import (
    SummarizeRequest,
    SummarizeResponse,
    EntityExtractionRequest,
    EntityExtractionResponse,
    BatchProcessRequest,
    BatchProcessResult,
)
from backend.modules.security.auth import get_current_user, require_role
from backend.modules.security.models import User

router = APIRouter()


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_text(request: SummarizeRequest, user: User = Depends(get_current_user)):
    """Summarize a text string."""
    try:
        return processing_service.summarize(request.text, request.max_length, request.style)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {e}")


@router.post("/extract-entities", response_model=EntityExtractionResponse)
async def extract_entities(request: EntityExtractionRequest, user: User = Depends(get_current_user)):
    """Extract entities from a text string."""
    try:
        return processing_service.extract_entities(request.text, request.entity_types)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Entity extraction failed: {e}")


@router.post("/batch", response_model=BatchProcessResult)
async def batch_process(request: BatchProcessRequest, user: User = Depends(require_role("contributor"))):
    """Run processing operations on ingested documents."""
    try:
        return processing_service.batch_process(request.doc_ids, request.operations)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {e}")


@router.get("/insights")
async def generate_insights(
    file_ids: Optional[str] = Query(None, description="Comma-separated file IDs to scope insights"),
    external_index_id: Optional[str] = Query(None, description="External index ID for BYOI insights"),
    user: User = Depends(get_current_user),
):
    """Generate insights — from uploaded files or an external index."""
    try:
        if external_index_id:
            result = processing_service.generate_insights_from_external(external_index_id)
        else:
            ids = file_ids.split(",") if file_ids else None
            result = processing_service.generate_insights(file_ids=ids)
        # Cache
        cache_key = external_index_id or file_ids or "all"
        try:
            from backend.storage.db_service import db_service
            db_service.save_insights(cache_key, result)
        except Exception:
            pass
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insights generation failed: {e}")


@router.get("/insights/cached")
async def get_cached_insights(user: User = Depends(get_current_user)):
    """Get cached insights (no regeneration)."""
    try:
        from backend.storage.db_service import db_service
        cached = db_service.load_insights("current")
        if cached:
            return cached
        return {"status": "no_cache"}
    except Exception:
        return {"status": "no_cache"}
