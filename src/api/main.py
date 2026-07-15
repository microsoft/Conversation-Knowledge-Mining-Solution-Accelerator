from contextlib import asynccontextmanager
import logging
import os
import time
import uuid
from collections import defaultdict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
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

# Configure logging
# Basic application logging (default: INFO level)
AZURE_BASIC_LOGGING_LEVEL = os.getenv("AZURE_BASIC_LOGGING_LEVEL", "INFO").upper()
# Azure package logging (default: WARNING level to suppress INFO)
AZURE_PACKAGE_LOGGING_LEVEL = os.getenv("AZURE_PACKAGE_LOGGING_LEVEL", "WARNING").upper()
# Azure logging packages (default: empty list)
AZURE_LOGGING_PACKAGES = [
    pkg.strip() for pkg in os.getenv("AZURE_LOGGING_PACKAGES", "").split(",") if pkg.strip()
]

# Basic config: logging.basicConfig(level=logging.INFO)
logging.basicConfig(
    level=getattr(logging, AZURE_BASIC_LOGGING_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress noisy Azure SDK internal loggers.
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies._universal").setLevel(logging.WARNING)
logging.getLogger("azure.cosmos").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)
# Suppress per-request HTTP logs (httpx logs every Content Understanding poll at INFO).
logging.getLogger("httpx").setLevel(logging.WARNING)

# Package config: Azure loggers set to WARNING to suppress INFO
for logger_name in AZURE_LOGGING_PACKAGES:
    logging.getLogger(logger_name).setLevel(getattr(logging, AZURE_PACKAGE_LOGGING_LEVEL, logging.WARNING))


def _parse_origins(raw: str) -> list[str]:
    parts = [p.strip().rstrip("/") for p in (raw or "").split(",")]
    return [p for p in parts if p]


# ── Rate Limiter ──────────────────────────────────────────────
_RATE_LIMIT = 60          # max requests per window
_RATE_WINDOW_SEC = 60     # window size in seconds
_rate_buckets: dict[str, list[float]] = defaultdict(list)
_EXEMPT_PATHS = frozenset({"/", "/api/health", "/openapi.json", "/docs", "/redoc"})
_SCAN_BLOCK_PATH_FRAGMENTS = (
    "${jndi:",
    "struts2-showcase",
    "/cgi-bin/",
    "/jspwiki/",
    "/broker/xml",
    "/portal/info.jsp",
    "/webtools/control/main",
)
_SCAN_BLOCK_EXACT_PATHS = frozenset({"/:undefined", "/:undefined/", "/undefined"})


class ScannerProbeBlockMiddleware(BaseHTTPMiddleware):
    """Block obvious vulnerability scanner probes early to reduce noisy logs."""

    async def dispatch(self, request: Request, call_next):
        path = (request.url.path or "").lower()
        query = (request.url.query or "").lower()
        raw = request.url.path

        if path in _SCAN_BLOCK_EXACT_PATHS:
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        if any(fragment in path for fragment in _SCAN_BLOCK_PATH_FRAGMENTS):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        if "${jndi:" in query:
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        # Catch encoded variants that appear in raw path (e.g. /%3Aundefined)
        if "%3aundefined" in raw.lower() or "%24%7bjndi%3a" in raw.lower():
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter keyed by client IP."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )
        now = time.monotonic()
        cutoff = now - _RATE_WINDOW_SEC
        bucket = _rate_buckets[client_ip] = [t for t in _rate_buckets[client_ip] if t > cutoff]

        if len(bucket) >= _RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"error": "RATE_LIMIT_EXCEEDED", "detail": f"Max {_RATE_LIMIT} requests per {_RATE_WINDOW_SEC}s"},
                headers={"Retry-After": str(_RATE_WINDOW_SEC)},
            )
        bucket.append(now)
        return await call_next(request)


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
    # Startup: avoid eager ingestion service warm-up to prevent startup/import deadlocks.

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

# CORS: restrict to frontend hostname in production, allow localhost for dev
_settings = get_settings()
_allowed_origins = []
if _settings.app_frontend_hostname:
    _allowed_origins = _parse_origins(_settings.app_frontend_hostname)

_is_prod = _settings.app_env.lower() in ("prod", "production")
if _is_prod and not _allowed_origins:
    raise RuntimeError("Production requires app_frontend_hostname for CORS allowlist.")

if not _allowed_origins and _settings.app_env in ("", "development", "local"):
    _allowed_origins = ["http://localhost:3000", "http://localhost:8080"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(ScannerProbeBlockMiddleware)
app.add_middleware(RateLimitMiddleware)

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
async def root():
    return {"status": "healthy", "service": "Knowledge Mining Platform"}


@app.get("/api/health", tags=["Health"])
async def health_check():
    """Deep health check — verifies SQL, Cosmos, and Search connectivity."""
    checks: dict[str, str] = {}
    healthy = True

    # SQL
    try:
        from src.api.storage.sql_service import sql_service
        checks["sql"] = "ok" if sql_service.available else "unavailable"
        if not sql_service.available:
            healthy = False
    except Exception as e:
        checks["sql"] = f"error: {e}"
        healthy = False

    # Azure AI Search
    try:
        settings = get_settings()
        checks["search"] = "configured" if settings.azure_search_endpoint else "not configured"
    except Exception as e:
        checks["search"] = f"error: {e}"

    # Cosmos
    try:
        from src.api.storage.cosmos_service import cosmos_service
        checks["cosmos"] = "ok" if cosmos_service.available else "unavailable"
    except Exception as e:
        checks["cosmos"] = f"error: {e}"

    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "healthy" if healthy else "degraded", "checks": checks, "version": app.version},
    )


# ── Structured error handlers ────────────────────────────────
_STATUS_LABELS = {
    400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN",
    404: "NOT_FOUND", 409: "CONFLICT", 413: "PAYLOAD_TOO_LARGE",
    429: "RATE_LIMIT_EXCEEDED", 500: "INTERNAL_SERVER_ERROR", 503: "SERVICE_UNAVAILABLE",
}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    rid = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": _STATUS_LABELS.get(exc.status_code, f"HTTP_{exc.status_code}"), "detail": exc.detail, "request_id": rid},
        headers={"X-Request-ID": rid} if rid else {},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    rid = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=422,
        content={"error": "VALIDATION_ERROR", "detail": exc.errors(), "request_id": rid},
        headers={"X-Request-ID": rid} if rid else {},
    )
