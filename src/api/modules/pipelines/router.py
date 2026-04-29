from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.api.modules.pipelines.engine import pipeline_engine
from src.api.modules.pipelines.models import (
    PipelineConfig,
    PipelineRunRequest,
    PipelineRunResult,
    PipelineUploadRequest,
    PipelineValidationResult,
    PipelineRegistryEntry,
    AutoProcessingConfig,
    GenerateConfigRequest,
    ProcessingStatus,
)
from src.api.modules.security.auth import get_current_user, require_role
from src.api.modules.security.models import User

router = APIRouter()


# ── Capabilities ──────────────────────────────────────────────

@router.get("/capabilities")
async def get_capabilities(user: User = Depends(get_current_user)):
    """List all registered capabilities."""
    from src.api.capabilities import list_capabilities
    return {"capabilities": list_capabilities()}


# ── Registry ──────────────────────────────────────────────────

@router.get("/", response_model=list[PipelineConfig])
async def list_pipelines(source: Optional[str] = None, user: User = Depends(get_current_user)):
    """List pipelines, optionally filtered by source (system/user/template/generated)."""
    return pipeline_engine.list_pipelines(source)


@router.get("/registry", response_model=list[PipelineRegistryEntry])
async def get_registry(user: User = Depends(get_current_user)):
    """Get pipeline registry with metadata."""
    return pipeline_engine.get_registry()


@router.get("/history", response_model=list[PipelineRunResult])
async def get_run_history(limit: int = 20, user: User = Depends(get_current_user)):
    """Get recent pipeline run history."""
    return pipeline_engine.get_run_history(limit)


@router.get("/{name}", response_model=PipelineConfig)
async def get_pipeline(name: str, user: User = Depends(get_current_user)):
    pipeline = pipeline_engine.get_pipeline(name)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found")
    return pipeline


# ── Execution ─────────────────────────────────────────────────

@router.post("/run", response_model=PipelineRunResult)
async def run_pipeline(request: PipelineRunRequest, user: User = Depends(require_role("contributor"))):
    """Execute a named pipeline."""
    return pipeline_engine.run_pipeline(request.pipeline_name, request.parameters)


# ── User config management ────────────────────────────────────

@router.post("/validate", response_model=PipelineValidationResult)
async def validate_config(request: PipelineUploadRequest, user: User = Depends(get_current_user)):
    """Validate a YAML pipeline config without registering it."""
    return pipeline_engine.validate_yaml(request.yaml_content)


@router.post("/upload", response_model=PipelineValidationResult)
async def upload_pipeline(request: PipelineUploadRequest, user: User = Depends(require_role("contributor"))):
    """Upload, validate, and register a user pipeline config."""
    result = pipeline_engine.register_user_pipeline(request.yaml_content)
    if not result.valid:
        raise HTTPException(status_code=400, detail=result.errors)
    return result


# ── Auto-generation ───────────────────────────────────────────

@router.post("/generate", response_model=PipelineConfig)
async def generate_default_config(
    request: GenerateConfigRequest = GenerateConfigRequest(),
    user: User = Depends(require_role("contributor")),
):
    """Auto-generate a pipeline config based on detected document types."""
    return pipeline_engine.generate_default_config(request.name, request.doc_types)


# ── Automation ────────────────────────────────────────────────

@router.get("/automation/config", response_model=AutoProcessingConfig)
async def get_auto_config(user: User = Depends(get_current_user)):
    return pipeline_engine.get_auto_config()


@router.put("/automation/config", response_model=AutoProcessingConfig)
async def set_auto_config(config: AutoProcessingConfig, user: User = Depends(require_role("contributor"))):
    pipeline_engine.set_auto_config(config)
    return config


@router.get("/status", response_model=ProcessingStatus)
async def get_processing_status(user: User = Depends(get_current_user)):
    """Get current processing status (snapshot)."""
    return pipeline_engine.get_processing_status()


@router.get("/status/stream")
async def stream_processing_status():
    """SSE stream of processing status updates. No auth required for event streams."""
    import asyncio

    queue = pipeline_engine.subscribe_sse()

    async def event_generator():
        # Send current status immediately
        initial = pipeline_engine.get_processing_status()
        yield f"data: {initial.model_dump_json()}\n\n"
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"  # Prevent connection timeout
        except asyncio.CancelledError:
            pass
        finally:
            pipeline_engine.unsubscribe_sse(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/preview/{name}")
async def preview_pipeline(name: str, user: User = Depends(get_current_user)):
    """Preview pipeline steps and validate before execution."""
    preview = pipeline_engine.preview_pipeline(name)
    if not preview:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found")
    return preview


# ── Admin ─────────────────────────────────────────────────────

@router.post("/reload")
async def reload_pipelines(user: User = Depends(require_role("admin"))):
    """Reload pipeline configurations from disk."""
    pipeline_engine.reload_pipelines()
    return {"message": "Pipelines reloaded", "count": len(pipeline_engine.list_pipelines())}
