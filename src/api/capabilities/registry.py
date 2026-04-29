from typing import Any, Callable

_registry: dict[str, Callable] = {}


def register(name: str):
    """Decorator to register a capability."""
    def wrapper(fn: Callable):
        _registry[name] = fn
        return fn
    return wrapper


def get_capability(name: str) -> Callable:
    fn = _registry.get(name)
    if not fn:
        raise ValueError(f"Unknown capability: '{name}'. Available: {sorted(_registry.keys())}")
    return fn


def list_capabilities() -> list[str]:
    return sorted(_registry.keys())
