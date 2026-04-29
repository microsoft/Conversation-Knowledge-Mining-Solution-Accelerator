from pydantic import BaseModel
from typing import Any, Optional


# ── Step classification ───────────────────────────────────────
SYSTEM_STEP_TYPES = {"ingest", "index", "index_filtered", "chunk"}
CAPABILITY_NAMES = {"generate", "embed", "search", "summarize", "extract_entities", "classify", "transform", "select"}


class PipelineContext(BaseModel):
    """Structured execution context — no random keys allowed."""
    step_outputs: dict[str, Any] = {}
    filtered_doc_ids: Optional[list[str]] = None
    metadata: dict[str, Any] = {}


class PipelineConfig(BaseModel):
    name: str
    description: str
    steps: list[dict[str, Any]]
    source: str = "system"
    version: int = 1
    created_at: Optional[str] = None
    auto_trigger: bool = False
    input_types: list[str] = []
    tags: list[str] = []
    priority: int = 0
    defaults: Optional[dict[str, Any]] = None
    on_error: Optional[dict[str, Any]] = None
    outputs: Optional[dict[str, Any]] = None

    def validate_steps(self) -> list[str]:
        errors: list[str] = []
        for i, step in enumerate(self.steps):
            if "name" not in step:
                errors.append(f"Step {i}: missing 'name'")
            kind = step.get("kind")
            if kind == "system":
                if step.get("type") not in SYSTEM_STEP_TYPES:
                    errors.append(f"Step {i}: unknown system type '{step.get('type')}'")
            elif kind == "capability":
                if step.get("capability") not in CAPABILITY_NAMES:
                    errors.append(f"Step {i}: unknown capability '{step.get('capability')}'")
            else:
                # Legacy: infer from type/capability field
                t = step.get("type") or step.get("capability")
                if t and t not in (SYSTEM_STEP_TYPES | CAPABILITY_NAMES):
                    errors.append(f"Step {i}: unknown step '{t}'")
        return errors


class PipelineRunRequest(BaseModel):
    pipeline_name: str
    parameters: Optional[dict[str, Any]] = None


class PipelineStepResult(BaseModel):
    step_name: str
    status: str  # "success" | "error" | "skipped" | "running"
    message: str
    data: Optional[Any] = None
    duration_ms: Optional[int] = None


class PipelineRunResult(BaseModel):
    pipeline_name: str
    status: str
    steps: list[PipelineStepResult]
    total_duration_ms: Optional[int] = None
    triggered_by: str = "manual"  # manual | auto | api


class PipelineUploadRequest(BaseModel):
    yaml_content: str


class PipelineValidationResult(BaseModel):
    valid: bool
    errors: list[str]
    config: Optional[PipelineConfig] = None


class PipelineRegistryEntry(BaseModel):
    name: str
    description: str
    source: str
    version: int
    step_count: int
    auto_trigger: bool
    created_at: Optional[str] = None


class AutoProcessingConfig(BaseModel):
    enabled: bool = True
    default_pipeline: str = "full_knowledge_mining"
    auto_select: bool = True  # Smart pipeline selection based on doc types


class ProcessingStatus(BaseModel):
    state: str  # idle | processing | completed | error
    pipeline_name: Optional[str] = None
    current_step: Optional[str] = None
    progress: int = 0  # 0-100
    total_steps: int = 0
    completed_steps: int = 0
    message: str = ""
    result: Optional[PipelineRunResult] = None


class GenerateConfigRequest(BaseModel):
    name: Optional[str] = None
    doc_types: Optional[list[str]] = None  # Override detected types
