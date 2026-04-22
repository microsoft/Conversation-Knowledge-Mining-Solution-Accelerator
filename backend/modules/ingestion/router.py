import json
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks

from backend.modules.ingestion.service import ingestion_service
from backend.modules.ingestion.models import Document, IngestionResult, IngestionStats, UploadedFile, FilterSchema, QuickInsights
from backend.modules.security.auth import get_current_user, require_role
from backend.modules.security.models import User

router = APIRouter()

DOCUMENT_EXTENSIONS = {"pdf", "docx", "xlsx", "txt", "png", "jpg", "jpeg", "tiff", "bmp"}


def _trigger_auto_pipeline():
    """Background task: trigger automated pipeline after upload."""
    from backend.modules.pipelines.engine import pipeline_engine
    pipeline_engine.trigger_auto_pipeline()


@router.post("/load-default", response_model=IngestionResult)
async def load_default_dataset(
    background_tasks: BackgroundTasks,
    user: User = Depends(require_role("contributor")),
):
    """Load the default synthetic dataset from Sample_Data/."""
    try:
        result = ingestion_service.load_default_dataset()
        background_tasks.add_task(_trigger_auto_pipeline)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Dataset file not found: {e}")


@router.post("/upload/json", response_model=IngestionResult)
async def upload_json(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(require_role("contributor")),
):
    """Upload and ingest a JSON file."""
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files accepted")
    content = await file.read()
    data = json.loads(content)
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="JSON must be an array of documents")
    result = ingestion_service.load_json_data(data, filename=file.filename or "uploaded.json")
    background_tasks.add_task(ingestion_service.finalize_ingestion, data, file.filename or "uploaded.json")
    background_tasks.add_task(_trigger_auto_pipeline)
    return result


@router.post("/upload/document", response_model=IngestionResult)
async def upload_document(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    user: User = Depends(require_role("contributor")),
):
    """Upload one or more PDF, DOCX, image, or text files.
    Text extraction happens synchronously; enrichment runs in background."""
    import io
    from backend.modules.document_intelligence.service import content_understanding_service

    all_data: list[dict] = []

    for file in files:
        filename = file.filename or "document"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in DOCUMENT_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: .{ext}. Accepted: {', '.join(sorted(DOCUMENT_EXTENSIONS))}",
            )

        content = await file.read()

        # Extract text (synchronous — required to create the document)
        try:
            extracted = content_understanding_service.analyze(
                file=io.BytesIO(content), filename=filename, analyzer="prebuilt-document"
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Content extraction failed for {filename}: {e}")

        if not extracted.markdown.strip():
            raise HTTPException(status_code=400, detail=f"No text could be extracted from {filename}")

        doc_id = filename.rsplit(".", 1)[0].replace(" ", "_")
        all_data.append({
            "id": doc_id,
            "type": ext,
            "text": extracted.markdown,
            "metadata": {
                "source_file": filename,
                "source_type": ext,
                "page_count": str(extracted.page_count),
            },
        })

    # Ingest each document individually (fast — just in-memory + SQL persist)
    total_loaded = 0
    for doc_data in all_data:
        doc_filename = doc_data.get("metadata", {}).get("source_file", "document")
        result = ingestion_service.load_json_data([doc_data], filename=doc_filename)
        total_loaded += result.total_loaded

    # Heavy work in background: AI enrichment, search indexing, pipeline
    for doc_data in all_data:
        doc_filename = doc_data.get("metadata", {}).get("source_file", "document")
        background_tasks.add_task(ingestion_service.finalize_ingestion, [doc_data], doc_filename)
    background_tasks.add_task(_trigger_auto_pipeline)

    return IngestionResult(
        total_loaded=total_loaded,
        by_type={d.get("type", "unknown"): 1 for d in all_data},
        sample_ids=[d["id"] for d in all_data[:5]],
    )


@router.post("/upload/csv", response_model=IngestionResult)
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(require_role("contributor")),
):
    """Upload and ingest a CSV file."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files accepted")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    tmp.write(await file.read())
    tmp.close()
    try:
        result = ingestion_service.load_csv_file(tmp.name)
    finally:
        os.unlink(tmp.name)
    background_tasks.add_task(_trigger_auto_pipeline)
    return result


@router.get("/documents", response_model=list[Document])
async def list_documents(
    type: Optional[str] = None,
    product: Optional[str] = None,
    category: Optional[str] = None,
    query: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    """Search / filter ingested documents."""
    return ingestion_service.search_documents(
        doc_type=type, product=product, category=category, query=query
    )


@router.get("/documents/{doc_id}", response_model=Document)
async def get_document(doc_id: str, user: User = Depends(get_current_user)):
    doc = ingestion_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/stats", response_model=IngestionStats)
async def get_stats(user: User = Depends(get_current_user)):
    return ingestion_service.get_stats()


@router.get("/filters")
async def get_available_filters(user: User = Depends(get_current_user)):
    """Return dynamically detected metadata filter values."""
    return ingestion_service.get_available_filters()


@router.get("/files", response_model=list[UploadedFile])
async def list_uploaded_files(user: User = Depends(get_current_user)):
    """Return list of uploaded files (document-level view)."""
    return ingestion_service.uploaded_files


@router.get("/extraction", response_model=FilterSchema)
async def get_filter_schema(user: User = Depends(get_current_user)):
    """Return the AI-generated filter schema with dimensions and values."""
    return ingestion_service.filter_schema


@router.delete("/clear")
async def clear_documents(user: User = Depends(get_current_user)):
    ingestion_service.clear()
    return {"message": "All documents, files, and filters cleared"}


@router.delete("/files/{file_id}")
async def delete_file(file_id: str, user: User = Depends(require_role("contributor"))):
    """Delete an uploaded file and all its documents from memory, SQL, and AI Search."""
    success = ingestion_service.delete_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found")
    # Return updated schema so frontend can refresh filters without a separate call
    return {
        "deleted": True,
        "file_id": file_id,
        "updated_schema": ingestion_service.filter_schema.dict(),
    }


# ══════════════════════════════════════════════
# External Index (Bring Your Own Index)
# ══════════════════════════════════════════════

from backend.modules.ingestion.external_index import (
    external_index_service, ConnectIndexRequest, ExternalIndex,
)


@router.post("/external/connect", response_model=ExternalIndex)
async def connect_external_index(
    request: ConnectIndexRequest,
    user: User = Depends(require_role("contributor")),
):
    """Connect to an existing Azure AI Search index."""
    try:
        return external_index_service.connect(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/external/indexes", response_model=list[ExternalIndex])
async def list_external_indexes(user: User = Depends(get_current_user)):
    """List all connected external indexes."""
    return external_index_service.list_all()


@router.delete("/external/{index_id}")
async def disconnect_external_index(
    index_id: str,
    user: User = Depends(require_role("contributor")),
):
    """Disconnect an external index."""
    success = external_index_service.disconnect(index_id)
    if not success:
        raise HTTPException(status_code=404, detail="Index not found")
    return {"disconnected": True}


@router.post("/external/{index_id}/search")
async def search_external_index(
    index_id: str,
    query: str,
    top_k: int = 5,
    user: User = Depends(get_current_user),
):
    """Search an external index."""
    results = external_index_service.search(index_id, query, top_k)
    return {"results": results}
