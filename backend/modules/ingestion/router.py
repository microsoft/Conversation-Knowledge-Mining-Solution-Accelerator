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
    background_tasks.add_task(_trigger_auto_pipeline)
    return result


@router.post("/upload/document", response_model=IngestionResult)
async def upload_document(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    user: User = Depends(require_role("contributor")),
):
    """Upload one or more PDF, DOCX, image, or text files.
    Pipeline: Content Understanding → AI Enrichment → Search Index + Storage."""
    import io
    from backend.modules.document_intelligence.service import content_understanding_service

    all_data: list[dict] = []
    first_filename = ""

    for file in files:
        filename = file.filename or "document"
        if not first_filename:
            first_filename = filename
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in DOCUMENT_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: .{ext}. Accepted: {', '.join(sorted(DOCUMENT_EXTENSIONS))}",
            )

        content = await file.read()

        # Step 1: Content Understanding — extract text, layout, fields
        try:
            extracted = content_understanding_service.analyze(
                file=io.BytesIO(content), filename=filename, analyzer="prebuilt-document"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Content Understanding failed for {filename}: {e}")

        if not extracted.markdown.strip():
            raise HTTPException(status_code=400, detail=f"No text could be extracted from {filename}")

        # Step 2: AI Enrichment — generate summary, entities, key phrases, topics
        try:
            extracted = content_understanding_service.enrich(extracted)
        except Exception:
            pass  # Non-blocking

        # Step 3: Create enriched document record
        doc_id = filename.rsplit(".", 1)[0].replace(" ", "_")
        all_data.append({
            "id": doc_id,
            "type": ext,
            "text": extracted.markdown,
            "summary": extracted.summary,
            "entities": extracted.entities,
            "key_phrases": extracted.key_phrases,
            "topics": extracted.topics,
            "metadata": {
                "source_file": filename,
                "source_type": ext,
                "page_count": str(extracted.page_count),
                **extracted.metadata_extracted,
            },
        })

    # Step 4: Ingest all documents together
    combined_filename = first_filename if len(files) == 1 else f"{len(files)}_documents"
    result = ingestion_service.load_json_data(all_data, filename=combined_filename)
    background_tasks.add_task(_trigger_auto_pipeline)

    # Build quick insights from enriched data
    summaries = [d.get("summary", "") for d in all_data if d.get("summary")]
    all_kp = []
    for d in all_data:
        all_kp.extend(d.get("key_phrases", []))
    all_topics = []
    for d in all_data:
        all_topics.extend(d.get("topics", []))
    all_entities = []
    for d in all_data:
        for e in d.get("entities", []):
            if isinstance(e, dict):
                all_entities.append(e.get("name", ""))
            elif isinstance(e, str):
                all_entities.append(e)

    # Detect content types from the extracted text
    detected = set()
    for d in all_data:
        text = d.get("text", "")
        if "|" in text and "---" in text:
            detected.add("Tables")
        if any(c.isdigit() for c in text[:500]):
            detected.add("Metrics")
        if d.get("entities"):
            detected.add("Key Entities")
        if d.get("key_phrases"):
            detected.add("Key Phrases")
        ext = d.get("type", "")
        if ext in ("pdf", "docx"):
            detected.add("Documents")
        if ext in ("png", "jpg", "jpeg", "tiff", "bmp"):
            detected.add("Images")

    # Build highlight bullets from summary
    highlights = []
    if summaries:
        for s in summaries[:3]:
            sentences = [sent.strip() for sent in s.replace(". ", ".\n").split("\n") if sent.strip()]
            highlights.extend(sentences[:2])
    highlights = highlights[:4]

    result.quick_insights = QuickInsights(
        summary=summaries[0] if summaries else "",
        highlights=highlights,
        detected=sorted(detected),
        keywords=sorted(set(all_kp))[:8],
    )

    return result


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
async def clear_documents(user: User = Depends(require_role("admin"))):
    ingestion_service.clear()
    return {"message": "All documents cleared"}


@router.delete("/files/{file_id}")
async def delete_file(file_id: str, user: User = Depends(require_role("contributor"))):
    """Delete an uploaded file and all its documents from memory, SQL, and AI Search."""
    success = ingestion_service.delete_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found")
    return {"deleted": True, "file_id": file_id}


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
