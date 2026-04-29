from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.modules.processing.service import processing_service
from src.api.modules.processing.models import (
    SummarizeRequest,
    SummarizeResponse,
    EntityExtractionRequest,
    EntityExtractionResponse,
    BatchProcessRequest,
    BatchProcessResult,
)
from src.api.modules.security.auth import get_current_user, require_role
from src.api.modules.security.models import User

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
    data_source_id: Optional[str] = Query(None, description="Data source ID for external DB insights"),
    refresh: bool = Query(False, description="Force regeneration instead of using cache"),
    user: User = Depends(get_current_user),
):
    """Generate insights — returns cached if available, regenerates if refresh=true."""
    cache_key = data_source_id or external_index_id or file_ids or "all"

    # Return cached insights unless refresh is requested
    if not refresh:
        try:
            from src.api.storage.db_service import db_service
            cached = db_service.load_insights(cache_key)
            if cached:
                return cached
        except Exception:
            pass

    try:
        if data_source_id:
            result = processing_service.generate_insights_from_data_source(data_source_id)
        elif external_index_id:
            result = processing_service.generate_insights_from_external(external_index_id)
        else:
            ids = file_ids.split(",") if file_ids else None
            result = processing_service.generate_insights(file_ids=ids)
        # Cache
        try:
            from src.api.storage.db_service import db_service
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
        from src.api.storage.db_service import db_service
        cached = db_service.load_insights("current")
        if cached:
            return cached
        return {"status": "no_cache"}
    except Exception:
        return {"status": "no_cache"}
