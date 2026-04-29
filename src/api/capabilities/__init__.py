# 8 atomic, reusable capabilities — standardized {result, meta} output
from src.api.capabilities import (  # noqa: F401
    transform,
)
from src.api.capabilities.registry import get_capability, list_capabilities
from src.api.capabilities import classify, embed, extract_entities, generate, search, select, summarize  # noqa: F401
