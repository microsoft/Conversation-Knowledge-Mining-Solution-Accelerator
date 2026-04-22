from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import backend.capabilities  # noqa: F401 — register all capabilities on startup

from backend.modules.ingestion.router import router as ingestion_router
from backend.modules.document_intelligence.router import router as docint_router
from backend.modules.embeddings.router import router as embeddings_router
from backend.modules.rag.router import router as rag_router
from backend.modules.processing.router import router as processing_router
from backend.modules.pipelines.router import router as pipelines_router
from backend.modules.security.auth import router as auth_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load data from SQL (or default dataset if empty)
    try:
        from backend.modules.ingestion.service import ingestion_service

        # Just load persisted data from SQL — don't re-ingest on every startup
        docs = ingestion_service.documents
        if docs:
            logger.info(f"Loaded {len(docs)} documents from database on startup")
        else:
            # First run with empty DB — load default dataset
            result = ingestion_service.load_default_dataset()
            logger.info(f"Auto-loaded {result.total_loaded} documents on startup")
    except Exception as e:
        logger.warning(f"Auto-load on startup failed: {e}")
    yield


app = FastAPI(
    title="Knowledge Mining Platform",
    description="Modular solution accelerator for knowledge mining across chats, FAQs, tickets, and audio transcripts.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register module routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(ingestion_router, prefix="/api/ingestion", tags=["Data Ingestion"])
app.include_router(docint_router, prefix="/api/documents", tags=["Document Intelligence"])
app.include_router(embeddings_router, prefix="/api/embeddings", tags=["Vector Embeddings"])
app.include_router(rag_router, prefix="/api/rag", tags=["RAG / Q&A"])
app.include_router(processing_router, prefix="/api/processing", tags=["Processing"])
app.include_router(pipelines_router, prefix="/api/pipelines", tags=["Configurable Pipelines"])


@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "Knowledge Mining Platform"}
