from contextlib import asynccontextmanager
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.config import get_settings

import src.api.capabilities  # noqa: F401 — register all capabilities on startup

from src.api.modules.ingestion.router import router as ingestion_router
from src.api.modules.document_intelligence.router import router as docint_router
from src.api.modules.embeddings.router import router as embeddings_router
from src.api.modules.rag.router import router as rag_router
from src.api.modules.processing.router import router as processing_router
from src.api.modules.pipelines.router import router as pipelines_router
from src.api.modules.security.auth import router as auth_router
from src.api.modules.data_sources.router import router as data_sources_router
from src.api.modules.insights.router import router as insights_router

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request for end-to-end tracing."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error(f"[{request_id}] Unhandled error on {request.method} {request.url.path}: {exc}")
            return JSONResponse(
                status_code=500,
                content={"error": "INTERNAL_SERVER_ERROR", "request_id": request_id},
                headers={"X-Request-ID": request_id},
            )
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load persisted data from SQL (if any)
    try:
        from src.api.modules.ingestion.service import ingestion_service

        docs = ingestion_service.documents
        if docs:
            logger.info(f"Loaded {len(docs)} documents from database on startup")
        else:
            logger.info("No existing data — users can upload or load demo from the Home page")
    except Exception as e:
        logger.warning(f"Startup data load failed: {e}")

    # Start queue worker for async document processing
    from src.api.modules.ingestion.queue_worker import queue_worker
    queue_worker.start()

    yield

    # Shutdown
    queue_worker.stop()


app = FastAPI(
    title="Knowledge Mining",
    description="Generic solution accelerator for knowledge mining all uploaded documents.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestIdMiddleware)

# Register module routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(ingestion_router, prefix="/api/ingestion", tags=["Data Ingestion"])
app.include_router(docint_router, prefix="/api/documents", tags=["Document Intelligence"])
app.include_router(embeddings_router, prefix="/api/embeddings", tags=["Vector Embeddings"])
app.include_router(rag_router, prefix="/api/rag", tags=["RAG / Q&A"])
app.include_router(processing_router, prefix="/api/processing", tags=["Processing"])
app.include_router(pipelines_router, prefix="/api/pipelines", tags=["Configurable Pipelines"])
app.include_router(data_sources_router, prefix="/api/data-sources", tags=["External Data Sources"])
app.include_router(insights_router, prefix="/api/insights", tags=["Insights Dashboard"])


@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "Knowledge Mining Platform"}
