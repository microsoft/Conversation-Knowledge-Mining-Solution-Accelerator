"""
FastAPI application entry point for the Conversation Knowledge Mining Solution Accelerator.

This module sets up the FastAPI app, configures middleware, loads environment variables,
registers API routers, and manages application lifespan events such as agent initialization
and cleanup.
"""


from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
import uvicorn

from agents.agent_factory import AgentFactory
from api.api_routes import router as backend_router
from api.history_routes import router as history_router

load_dotenv()


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """
    Manages the application lifespan events for the FastAPI app.

    On startup, initializes the Azure AI agent using the configuration and attaches it to the app state.
    On shutdown, deletes the agent instance and performs any necessary cleanup.
    """
    fastapi_app.state.agent = await AgentFactory.get_instance()
    yield
    await AgentFactory.delete_instance()
    fastapi_app.state.agent = None


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
