"""
FastAPI application entry point for the Conversation Knowledge Mining Solution Accelerator.

This module sets up the FastAPI app, configures middleware, loads environment variables,
registers API routers, and manages application lifespan events such as agent initialization
and cleanup.
"""


import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
import uvicorn

from agents.conversation_agent_factory import ConversationAgentFactory
from agents.search_agent_factory import SearchAgentFactory
from agents.sql_agent_factory import SQLAgentFactory
from agents.chart_agent_factory import ChartAgentFactory
from api.api_routes import router as backend_router
from api.history_routes import router as history_router

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

# Package config: Azure loggers set to WARNING to suppress INFO
for logger_name in AZURE_LOGGING_PACKAGES:
    logging.getLogger(logger_name).setLevel(getattr(logging, AZURE_PACKAGE_LOGGING_LEVEL, logging.WARNING))


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """
    Manages the application lifespan events for the FastAPI app.

    On startup, initializes the Azure AI agent using the configuration and attaches it to the app state.
    On shutdown, deletes the agent instance and performs any necessary cleanup.
    """
    fastapi_app.state.agent = await ConversationAgentFactory.get_agent()
    fastapi_app.state.search_agent = await SearchAgentFactory.get_agent()
    fastapi_app.state.sql_agent = await SQLAgentFactory.get_agent()
    fastapi_app.state.chart_agent = await ChartAgentFactory.get_agent()
    yield
    await ConversationAgentFactory.delete_agent()
    await SearchAgentFactory.delete_agent()
    await SQLAgentFactory.delete_agent()
    await ChartAgentFactory.delete_agent()
    fastapi_app.state.sql_agent = None
    fastapi_app.state.search_agent = None
    fastapi_app.state.agent = None
    fastapi_app.state.chart_agent = None


def build_app() -> FastAPI:
    """
    Creates and configures the FastAPI application instance.
    """
    fastapi_app = FastAPI(
        title="Conversation Knowledge Mining Solution Accelerator",
        version="1.0.0",
        lifespan=lifespan
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

    return fastapi_app


app = build_app()


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
