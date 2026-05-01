import json
import logging
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks

from src.api.modules.ingestion.service import ingestion_service
from src.api.modules.ingestion.models import Document, IngestionResult, IngestionStats, UploadedFile, FilterSchema
from src.api.modules.security.auth import get_current_user, require_role
from src.api.modules.security.models import User
from src.api.utils.constants import DOCUMENT_EXTENSIONS

logger = logging.getLogger(__name__)

router = APIRouter()


def _trigger_auto_pipeline():
    """Background task: trigger automated pipeline after upload."""
    from src.api.modules.pipelines.engine import pipeline_engine
    pipeline_engine.trigger_auto_pipeline()


@router.post("/load-default", response_model=IngestionResult)
async def load_default_dataset(
    background_tasks: BackgroundTasks,
    user: User = Depends(require_role("contributor")),
):
    """Load the default synthetic dataset from data/."""
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
    Files are saved to blob storage immediately; extraction and enrichment run via queue."""
    from datetime import datetime
    from src.api.modules.ingestion.azure_storage import azure_storage_service
    from src.api.modules.ingestion.queue_service import queue_service, EXTRACTION_QUEUE

    # Validate all files and read their content
    file_contents: list[tuple[str, str, bytes]] = []
    for file in files:
        filename = file.filename or "document"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in DOCUMENT_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: .{ext}. Accepted: {', '.join(sorted(DOCUMENT_EXTENSIONS))}",
            )
        content = await file.read()
        file_contents.append((filename, ext, content))

    # Save raw files to blob storage and create "processing" file records
    for filename, ext, content in file_contents:
        file_id = filename.rsplit(".", 1)[0].replace(" ", "_")

        # Skip if this document is already processed or currently processing
        ingestion_service._ensure_loaded()
        existing = ingestion_service._uploaded_files.get(file_id)
        if existing and existing.status in ("ready", "processing"):
            logger.info(f"Skipping {filename}: already {existing.status}")
            continue

        # Upload raw file to blob storage
        try:
            azure_storage_service.upload_raw_file(file_id, filename, content)
        except Exception as e:
            logger.warning(f"Raw blob upload failed for {filename}: {e}")

        # Create a placeholder file record
        uploaded_file = UploadedFile(
            id=file_id,
            filename=filename,
            doc_count=0,
            summary="Processing...",
            keywords=[],
            filter_values={},
            doc_ids=[],
            uploaded_at=datetime.utcnow().isoformat() + "Z",
            status="processing",
        )
        ingestion_service._ensure_loaded()
        ingestion_service._uploaded_files[file_id] = uploaded_file
        ingestion_service._persist_file(uploaded_file)

        # Enqueue for Stage 1 (extraction) — falls back to in-process if queue unavailable
        message = {"file_id": file_id, "filename": filename, "ext": ext, "blob_path": f"raw/{file_id}/{filename}"}
        if not queue_service.available or not queue_service.enqueue(EXTRACTION_QUEUE, message):
            logger.info(f"Queue unavailable, falling back to background task for {filename}")
            background_tasks.add_task(_process_single_document, file_id, filename, ext, content)

    return IngestionResult(
        total_loaded=0,
        by_type={ext: 1 for _, ext, _ in file_contents},
        sample_ids=[fname.rsplit(".", 1)[0].replace(" ", "_") for fname, _, _ in file_contents],
    )


def _process_single_document(file_id: str, filename: str, ext: str, content: bytes):
    """Process a single document — used as fallback when queue is unavailable.
    Runs the full pipeline: extract → chunk → embed → index → enrich."""
    import io
    from src.api.modules.document_intelligence.service import content_understanding_service
    from src.api.modules.ingestion.chunking import chunk_text

    try:
        # Stage 1: Extract
        extracted = content_understanding_service.analyze(
            file=io.BytesIO(content), filename=filename
        )

        if not extracted.markdown.strip():
            ingestion_service._update_file_status(file_id, "failed", error=f"No text could be extracted from {filename}")
            return

        doc_data = {
            "id": file_id,
            "type": ext,
            "text": extracted.markdown,
            "metadata": {
                "source_file": filename,
                "source_type": ext,
                "page_count": str(extracted.page_count),
            },
        }

        ingestion_service.load_json_data([doc_data], filename=filename)

        # Stage 2: Chunk + Embed + Index
        chunks = chunk_text(extracted.markdown)
        try:
            from src.api.modules.embeddings.service import EmbeddingsService
            from src.api.modules.ingestion.azure_storage import azure_storage_service

            emb_service = EmbeddingsService()
            embeddings = []
            for chunk in chunks:
                try:
                    emb = emb_service.generate_embedding(chunk)
                    embeddings.append(emb.embedding)
                except Exception:
                    embeddings.append([0.0] * 1536)

            azure_storage_service.index_chunks(
                doc_id=file_id, chunks=chunks, embeddings=embeddings,
                metadata=doc_data.get("metadata", {}),
            )
        except Exception as e:
            logger.warning(f"Chunk/embed/index failed (non-blocking): {e}")

        # Enrich
        ingestion_service.finalize_ingestion([doc_data], filename)
        ingestion_service._update_file_status(file_id, "ready")

    except Exception as e:
        logger.error(f"Processing failed for {filename}: {e}")
        ingestion_service._update_file_status(file_id, "failed", error=str(e))


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

from src.api.modules.ingestion.external_index import (
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
