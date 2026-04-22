import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

import yaml

from backend.config import get_settings
from backend.modules.ingestion.service import ingestion_service
from backend.capabilities.executor import execute_step
from backend.modules.pipelines.models import (
    PipelineConfig,
    PipelineContext,
    PipelineRunResult,
    PipelineStepResult,
    PipelineRegistryEntry,
    PipelineValidationResult,
    AutoProcessingConfig,
    ProcessingStatus,
    SYSTEM_STEP_TYPES,
)


class PipelineEngine:
    """Pipeline registry + execution engine with SSE status streaming."""

    def __init__(self):
        self._pipelines: dict[str, PipelineConfig] = {}
        self._run_history: list[PipelineRunResult] = []
        self._auto_config = AutoProcessingConfig()
        self._status = ProcessingStatus(state="idle")
        self._sse_subscribers: list[asyncio.Queue] = []
        self._system_registry = {
            "ingest": self._step_ingest,
            "index": self._step_index,
            "index_filtered": self._step_index_filtered,
            "chunk": self._step_chunk,
        }
        self._load_pipelines()

    # ── Registry ──────────────────────────────────────────────

    def _load_pipelines(self):
        settings = get_settings()
        config_dir = settings.pipelines_config_dir
        if not os.path.exists(config_dir):
            return
        for filename in os.listdir(config_dir):
            if filename.endswith((".yaml", ".yml")):
                filepath = os.path.join(config_dir, filename)
                with open(filepath, "r") as f:
                    data = yaml.safe_load(f)
                if data:
                    data.setdefault("source", "system")
                    data.setdefault("version", 1)
                    config = PipelineConfig(**data)
                    self._pipelines[config.name] = config

    def list_pipelines(self, source: Optional[str] = None) -> list[PipelineConfig]:
        pipelines = list(self._pipelines.values())
        if source:
            pipelines = [p for p in pipelines if p.source == source]
        return pipelines

    def get_registry(self) -> list[PipelineRegistryEntry]:
        return [
            PipelineRegistryEntry(
                name=p.name, description=p.description, source=p.source,
                version=p.version, step_count=len(p.steps),
                auto_trigger=p.auto_trigger, created_at=p.created_at,
            )
            for p in self._pipelines.values()
        ]

    def get_pipeline(self, name: str) -> Optional[PipelineConfig]:
        return self._pipelines.get(name)

    def get_run_history(self, limit: int = 20) -> list[PipelineRunResult]:
        return self._run_history[-limit:]

    # ── Validation ────────────────────────────────────────────

    def validate_yaml(self, yaml_content: str) -> PipelineValidationResult:
        """Validate a YAML pipeline config against the schema."""
        errors: list[str] = []
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            return PipelineValidationResult(valid=False, errors=[f"Invalid YAML: {e}"])

        if not isinstance(data, dict):
            return PipelineValidationResult(valid=False, errors=["Config must be a YAML mapping"])

        for field in ("name", "description", "steps"):
            if field not in data:
                errors.append(f"Missing required field: '{field}'")

        if "steps" in data:
            if not isinstance(data["steps"], list) or len(data["steps"]) == 0:
                errors.append("'steps' must be a non-empty list")
            else:
                config = PipelineConfig(**{**data, "source": "user"})
                errors.extend(config.validate_steps())

        if errors:
            return PipelineValidationResult(valid=False, errors=errors)

        config = PipelineConfig(
            **data, source=data.get("source", "user"),
            version=data.get("version", 1),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return PipelineValidationResult(valid=True, errors=[], config=config)

    # ── User config upload ────────────────────────────────────

    def register_user_pipeline(self, yaml_content: str) -> PipelineValidationResult:
        """Validate and register a user-uploaded pipeline config."""
        result = self.validate_yaml(yaml_content)
        if not result.valid or not result.config:
            return result

        config = result.config
        config.source = "user"
        config.created_at = datetime.now(timezone.utc).isoformat()

        # Version bumping
        existing = self._pipelines.get(config.name)
        if existing and existing.source == "user":
            config.version = existing.version + 1

        self._pipelines[config.name] = config

        # Persist to disk
        self._save_user_pipeline(config)
        return result

    def _save_user_pipeline(self, config: PipelineConfig):
        settings = get_settings()
        user_dir = os.path.join(settings.pipelines_config_dir, "user")
        os.makedirs(user_dir, exist_ok=True)
        filepath = os.path.join(user_dir, f"{config.name}.yaml")
        data = config.model_dump(exclude_none=True)
        with open(filepath, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    # ── Default config generation ─────────────────────────────

    def generate_default_config(self, name: Optional[str] = None, doc_types: Optional[list[str]] = None) -> PipelineConfig:
        """Auto-generate a pipeline based on detected document types."""
        if doc_types is None:
            stats = ingestion_service.get_stats()
            doc_types = list(stats.by_type.keys())

        pipeline_name = name or f"auto_{'_'.join(doc_types[:2])}" if doc_types else "auto_default"

        steps: list[dict[str, Any]] = [
            {"name": "ingest_data", "kind": "system", "type": "ingest"},
        ]

        if len(doc_types) == 1:
            steps.append({"name": "select_docs", "kind": "capability", "capability": "select", "params": {"where": {"type": doc_types[0]}}})
            steps.append({"name": "index_docs", "kind": "system", "type": "index_filtered"})
        else:
            steps.append({"name": "index_docs", "kind": "system", "type": "index"})

        steps.append({"name": "summarize_content", "kind": "capability", "capability": "summarize", "retry": 1})
        steps.append({"name": "extract_entities", "kind": "capability", "capability": "extract_entities", "retry": 1})

        config = PipelineConfig(
            name=pipeline_name,
            description=f"Auto-generated pipeline for: {', '.join(doc_types) or 'all documents'}",
            steps=steps,
            source="generated",
            version=1,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._pipelines[config.name] = config
        return config

    # ── SSE Status Streaming ────────────────────────────────

    def subscribe_sse(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._sse_subscribers.append(q)
        return q

    def unsubscribe_sse(self, q: asyncio.Queue):
        self._sse_subscribers = [s for s in self._sse_subscribers if s is not q]

    def _push_status(self, status: ProcessingStatus):
        self._status = status
        data = json.dumps(status.model_dump(), default=str)
        for q in self._sse_subscribers:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass  # drop if subscriber is slow

    # ── Automation ────────────────────────────────────────────

    def get_auto_config(self) -> AutoProcessingConfig:
        return self._auto_config

    def set_auto_config(self, config: AutoProcessingConfig):
        self._auto_config = config

    def get_processing_status(self) -> ProcessingStatus:
        return self._status

    def _select_best_pipeline(self) -> str:
        """Score-based pipeline selection using input_types, tags, and priority."""
        stats = ingestion_service.get_stats()
        doc_types = set(stats.by_type.keys())

        scored: list[tuple[str, int]] = []
        for name, config in self._pipelines.items():
            score = config.priority
            if config.input_types:
                score += len(doc_types & set(config.input_types)) * 10
            if config.tags:
                score += len(doc_types & set(config.tags)) * 5
            scored.append((name, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        if scored and scored[0][1] > 0:
            return scored[0][0]
        if "full_knowledge_mining" in self._pipelines:
            return "full_knowledge_mining"
        return self.generate_default_config().name

    def trigger_auto_pipeline(self) -> Optional[PipelineRunResult]:
        """Called after data upload — always processes automatically."""
        if not self._auto_config.enabled:
            return None

        if self._auto_config.auto_select:
            pipeline_name = self._select_best_pipeline()
        else:
            pipeline_name = self._auto_config.default_pipeline
            if pipeline_name not in self._pipelines:
                self.generate_default_config(name=pipeline_name)

        return self.run_pipeline(pipeline_name, triggered_by="auto")

    def preview_pipeline(self, name: str) -> Optional[dict]:
        """Preview a pipeline's steps without executing."""
        config = self._pipelines.get(name)
        if not config:
            return None
        return {
            "name": config.name,
            "description": config.description,
            "source": config.source,
            "version": config.version,
            "steps": [
                {
                    "name": s["name"],
                    "kind": s.get("kind", "system" if (s.get("type") or "") in SYSTEM_STEP_TYPES else "capability"),
                    "type": s.get("type") or s.get("capability", ""),
                    "params": s.get("params", {}),
                    "enabled": s.get("enabled", True),
                }
                for s in config.steps
            ],
            "warnings": config.validate_steps(),
        }

    # ── Execution ─────────────────────────────────────────────

    def run_pipeline(
        self, name: str, parameters: Optional[dict[str, Any]] = None, triggered_by: str = "manual"
    ) -> PipelineRunResult:
        config = self._pipelines.get(name)
        if not config:
            status = ProcessingStatus(state="error", pipeline_name=name, message=f"Pipeline '{name}' not found")
            self._push_status(status)
            result = PipelineRunResult(
                pipeline_name=name, status="error", triggered_by=triggered_by,
                steps=[PipelineStepResult(step_name="init", status="error", message=f"Pipeline '{name}' not found")],
            )
            self._run_history.append(result)
            return result

        total_steps = len(config.steps)
        self._push_status(ProcessingStatus(
            state="processing", pipeline_name=name, progress=0,
            total_steps=total_steps, completed_steps=0, message="Starting pipeline...",
        ))

        step_results: list[PipelineStepResult] = []
        ctx = PipelineContext(metadata=parameters or {})
        overall_status = "success"
        total_start = time.time()

        for i, step in enumerate(config.steps):
            step_name = step["name"]
            kind = step.get("kind")
            retry = step.get("retry", (config.defaults or {}).get("retry", 0))
            cache = step.get("cache", (config.defaults or {}).get("cache", False))
            step_params = dict(step.get("params", {}))
            enabled = step.get("enabled", True)

            if not enabled:
                step_results.append(PipelineStepResult(
                    step_name=step_name, status="skipped", message="Step disabled",
                ))
                continue

            # Resolve step type from kind
            if kind == "system":
                step_type = step.get("type", "")
                is_system = True
            elif kind == "capability":
                step_type = step.get("capability", "")
                is_system = False
            else:
                # Legacy: infer
                step_type = step.get("type") or step.get("capability") or ""
                is_system = step_type in SYSTEM_STEP_TYPES

            self._push_status(ProcessingStatus(
                state="processing", pipeline_name=name,
                current_step=step_name, progress=int((i / total_steps) * 100),
                total_steps=total_steps, completed_steps=i,
                message=f"Running: {step_name}",
            ))

            step_start = time.time()
            try:
                if is_system:
                    result = self._run_system_step(step_type, step_params, ctx)
                else:
                    cap_context = {"filtered_doc_ids": ctx.filtered_doc_ids, **ctx.metadata}
                    exec_step = {"capability": step_type, "params": step_params, "retry": retry, "cache": cache}
                    result = execute_step(exec_step, cap_context)
                    if "filtered_doc_ids" in cap_context:
                        ctx.filtered_doc_ids = cap_context["filtered_doc_ids"]

                ctx.step_outputs[step_name] = result
                duration = int((time.time() - step_start) * 1000)
                step_results.append(PipelineStepResult(
                    step_name=step_name, status="success",
                    message=f"Step '{step_type}' completed", data=result, duration_ms=duration,
                ))
            except Exception as e:
                duration = int((time.time() - step_start) * 1000)
                overall_status = "error"
                step_results.append(PipelineStepResult(
                    step_name=step_name, status="error",
                    message=f"Step '{step_type}' failed: {str(e)}", duration_ms=duration,
                ))
                error_strategy = (config.on_error or {}).get("strategy", "fail_fast")
                if error_strategy == "fail_fast":
                    break

        total_duration = int((time.time() - total_start) * 1000)
        run_result = PipelineRunResult(
            pipeline_name=name, status=overall_status, steps=step_results,
            total_duration_ms=total_duration, triggered_by=triggered_by,
        )
        self._run_history.append(run_result)

        self._push_status(ProcessingStatus(
            state="completed" if overall_status == "success" else "error",
            pipeline_name=name, progress=100,
            total_steps=total_steps, completed_steps=len(step_results),
            message=f"Pipeline {overall_status} in {total_duration}ms",
            result=run_result,
        ))
        return run_result

    # ── System Step Registry ─────────────────────────────────

    def _run_system_step(self, step_type: str, params: dict, ctx: PipelineContext) -> dict:
        fn = self._system_registry.get(step_type)
        if not fn:
            raise ValueError(f"Unknown system step: {step_type}")
        return fn(params, ctx)

    def _step_ingest(self, params: dict, ctx: PipelineContext) -> dict:
        result = ingestion_service.load_default_dataset()
        return {"result": {"total_loaded": result.total_loaded, "by_type": result.by_type}, "meta": {}}

    def _step_index(self, params: dict, ctx: PipelineContext) -> dict:
        return self._do_index(ctx, filtered_only=False)

    def _step_index_filtered(self, params: dict, ctx: PipelineContext) -> dict:
        return self._do_index(ctx, filtered_only=True)

    def _step_chunk(self, params: dict, ctx: PipelineContext) -> dict:
        total_docs = 0
        for doc in ingestion_service.documents.values():
            text = ingestion_service.normalize_text(doc)
            if text.strip():
                total_docs += 1
        return {"result": {"total_documents": total_docs}, "meta": {}}

    def _do_index(self, ctx: PipelineContext, filtered_only: bool = False) -> dict:
        from backend.capabilities.embed import embed
        from backend.storage.vector_store import vector_store

        doc_ids = ctx.filtered_doc_ids if filtered_only else None
        docs = ingestion_service.documents
        if doc_ids:
            docs = {k: v for k, v in docs.items() if k in doc_ids}

        errors: list[str] = []
        indexed = 0
        for doc_id, doc in docs.items():
            text = ingestion_service.normalize_text(doc)
            if not text.strip():
                continue
            try:
                emb_result = embed(text=text)
                vector_store.upsert(doc_id, emb_result["result"], text, {
                    "doc_id": doc_id, "type": doc.type,
                    "product": doc.metadata.product, "category": doc.metadata.category,
                })
                indexed += 1
            except Exception as e:
                errors.append(f"{doc_id}: {e}")
        return {"result": {"indexed_count": indexed}, "meta": {"errors": errors}}

    def reload_pipelines(self):
        self._pipelines.clear()
        self._load_pipelines()


pipeline_engine = PipelineEngine()
