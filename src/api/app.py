"""
FastAPI application entry point for the Conversation Knowledge Mining Solution Accelerator.

This module sets up the FastAPI app, configures middleware, loads environment variables,
and registers API routers.
"""


import logging
import os
from fastapi import FastAPI

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
import uvicorn

from api.api_routes import router as backend_router
from api.history_routes import router as history_router

# Configure Azure Monitor and OpenTelemetry imports
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from common.logging.span_filters import DropASGIResponseBodySpanProcessor, DropCosmosDependencySpanProcessor

# Load environment variables
load_dotenv()

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

# Suppress noisy Azure SDK and OpenTelemetry internal loggers.
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies._universal").setLevel(logging.WARNING)
logging.getLogger("azure.cosmos").setLevel(logging.WARNING)
logging.getLogger("opentelemetry.sdk").setLevel(logging.WARNING)
logging.getLogger("azure.monitor.opentelemetry.exporter.export._base").setLevel(logging.WARNING)

# Package config: Azure loggers set to WARNING to suppress INFO
for logger_name in AZURE_LOGGING_PACKAGES:
    logging.getLogger(logger_name).setLevel(getattr(logging, AZURE_PACKAGE_LOGGING_LEVEL, logging.WARNING))



def build_app() -> FastAPI:
    """
    Creates and configures the FastAPI application instance.
    """
    fastapi_app = FastAPI(
        title="Conversation Knowledge Mining Solution Accelerator",
        version="1.0.0"
    )

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    fastapi_app.include_router(backend_router, prefix="/api", tags=["backend"])
    fastapi_app.include_router(history_router, prefix="/history", tags=["history"])

    @fastapi_app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy"}

    # Configure Azure Monitor and instrument FastAPI for OpenTelemetry
    # This enables automatic request tracing, dependency tracking, and proper operation_id
    instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if instrumentation_key:
        # Configure Application Insights telemetry with live metrics
        configure_azure_monitor(
            connection_string=instrumentation_key,
            enable_live_metrics=True,
            span_processors=[
                DropASGIResponseBodySpanProcessor(),
                DropCosmosDependencySpanProcessor()
            ]
        )

        # Instrument FastAPI app — exclude health-check URL to reduce telemetry noise
        FastAPIInstrumentor.instrument_app(
            fastapi_app,
            excluded_urls="health"
        )
        logger.info("Application Insights configured with live metrics and FastAPI instrumentation enabled")
    else:
        logger.warning("No Application Insights connection string found. Telemetry disabled.")

    return fastapi_app


app = build_app()


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
