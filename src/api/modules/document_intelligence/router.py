from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from src.api.modules.document_intelligence.service import content_understanding_service
from src.api.modules.document_intelligence.models import ExtractedDocument
from src.api.modules.security.auth import require_role
from src.api.modules.security.models import User

router = APIRouter()


@router.post("/extract", response_model=ExtractedDocument)
async def extract_content(
    file: UploadFile = File(...),
    analyzer: str = "prebuilt-document",
    user: User = Depends(require_role("contributor")),
):
    """Extract content from an uploaded file using Azure Content Understanding."""
    try:
        return content_understanding_service.analyze(file.file, file.filename, analyzer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Content analysis failed: {e}")
