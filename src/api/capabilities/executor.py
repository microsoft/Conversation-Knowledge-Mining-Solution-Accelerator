import time
import hashlib
import json
from typing import Any
from src.api.capabilities.registry import get_capability

_cache: dict[str, Any] = {}


def execute_step(step: dict, context: dict) -> Any:
    """Execute a single pipeline step with retry and cache support."""
    capability_name = step.get("capability") or step.get("action")
    params = dict(step.get("params", step.get("parameters", {})))
    retry_count = step.get("retry", 0)
    use_cache = step.get("cache", False)

    fn = get_capability(capability_name)

    # Cache check
    if use_cache:
        cache_key = _make_cache_key(capability_name, params)
        if cache_key in _cache:
            return _cache[cache_key]

    # Execute with retry
    last_error: Exception | None = None
    for attempt in range(retry_count + 1):
        try:
            result = fn(**params, context=context)
            if use_cache:
                _cache[_make_cache_key(capability_name, params)] = result
            return result
        except Exception as e:
            last_error = e
            if attempt < retry_count:
                time.sleep(1 * (attempt + 1))

    raise last_error  # type: ignore


def _make_cache_key(capability: str, params: dict) -> str:
    serializable = {k: v for k, v in params.items() if k != "context"}
    return hashlib.md5(f"{capability}:{json.dumps(serializable, sort_keys=True, default=str)}".encode()).hexdigest()
