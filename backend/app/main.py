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
from backend.modules.data_sources.router import router as data_sources_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load persisted data from SQL (if any)
    try:
        from backend.modules.ingestion.service import ingestion_service

        docs = ingestion_service.documents
        if docs:
            logger.info(f"Loaded {len(docs)} documents from database on startup")
        else:
            logger.info("No existing data — users can upload or load demo from the Home page")
    except Exception as e:
        logger.warning(f"Startup data load failed: {e}")

    # Auto-connect data sources from .env
    try:
        from backend.config import get_settings
        import json
        settings = get_settings()
        if settings.data_sources:
            from backend.modules.data_sources.registry import data_source_registry
            from backend.modules.data_sources.base import DataSourceConfig, DataSourceType, AuthMethod, QueryMode, FieldMapping

            sources_config = json.loads(settings.data_sources)
            existing = {s.name for s in data_source_registry.list_all()}
            for src in sources_config:
                if src.get("name") in existing:
                    logger.info(f"Data source '{src['name']}' already connected, skipping")
                    continue
                try:
                    config = DataSourceConfig(
                        name=src["name"],
                        source_type=DataSourceType(src.get("source_type", "sql")),
                        connection_string=src.get("connection_string", ""),
                        endpoint=src.get("endpoint", ""),
                        database=src.get("database", ""),
                        table_or_query=src.get("table_or_query", ""),
                        auth_method=AuthMethod(src.get("auth_method", "managed_identity")),
                        field_mapping=FieldMapping(**src["field_mapping"]) if "field_mapping" in src else FieldMapping(),
                        query_mode=QueryMode(src.get("query_mode", "both")),
                    )
                    result = data_source_registry.create(config)
                    logger.info(f"Auto-connected data source '{result.name}' ({result.status}, {result.doc_count} rows)")
                except Exception as e:
                    logger.warning(f"Failed to auto-connect data source '{src.get('name', '?')}': {e}")
    except Exception as e:
        if "data_sources" not in str(e):
            logger.warning(f"Data source auto-connect failed: {e}")

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
app.include_router(data_sources_router, prefix="/api/data-sources", tags=["External Data Sources"])


@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "Knowledge Mining Platform"}
