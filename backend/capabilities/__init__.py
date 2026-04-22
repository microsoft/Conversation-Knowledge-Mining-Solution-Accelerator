# 8 atomic, reusable capabilities — standardized {result, meta} output
from backend.capabilities import (  # noqa: F401
    generate,
    embed,
    search,
    summarize,
    extract_entities,
    classify,
    transform,
    select,
)
from backend.capabilities.registry import get_capability, list_capabilities  # noqa: F401
