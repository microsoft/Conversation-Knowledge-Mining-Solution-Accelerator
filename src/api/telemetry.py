"""Process-wide telemetry singletons.

A single :class:`TokenUsageEmitter` is constructed at import time so every
router/utility shares the same App Insights connection-string resolution and
static dimensions.

Optional environment variables
------------------------------
LLM_TOKEN_SAMPLE_RATE
    Float in [0, 1]. Fraction of high-cardinality token events
    (agent/model/user/team/speech) to ship. The summary event always fires.
    Defaults to ``1.0``.

LLM_TOKEN_USER_ID_HMAC_KEY
    When set, ``user_id`` values are replaced with an HMAC-SHA256 hex digest
    (truncated to 16 chars) before leaving the process.

LLM_TOKEN_PRICING
    Optional comma-separated list of ``model=in_per_1k:out_per_1k`` entries,
    e.g. ``gpt-4o=0.0025:0.01,gpt-4o-mini=0.00015:0.0006``.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Callable, Optional

from common.logging.llm_token_telemetry import TokenUsageEmitter

_log = logging.getLogger(__name__)


def _parse_sample_rate() -> float:
    raw = os.getenv("LLM_TOKEN_SAMPLE_RATE")
    if not raw:
        return 1.0
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        _log.warning("Invalid LLM_TOKEN_SAMPLE_RATE=%r; defaulting to 1.0", raw)
        return 1.0


def _build_user_id_hasher() -> Optional[Callable[[str], str]]:
    key = os.getenv("LLM_TOKEN_USER_ID_HMAC_KEY")
    if not key:
        return None
    key_bytes = key.encode("utf-8")

    def _hash(value: str) -> str:
        digest = hmac.new(key_bytes, value.encode("utf-8"), hashlib.sha256).hexdigest()
        return digest[:16]

    return _hash


def _parse_pricing() -> dict[str, tuple[float, float]]:
    raw = os.getenv("LLM_TOKEN_PRICING")
    if not raw:
        return {}
    pricing: dict[str, tuple[float, float]] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or "=" not in entry:
            continue
        model, rates = entry.split("=", 1)
        if ":" not in rates:
            continue
        in_s, out_s = rates.split(":", 1)
        try:
            pricing[model.strip().lower()] = (float(in_s), float(out_s))
        except ValueError:
            _log.warning("Ignoring malformed pricing entry: %s", entry)
    return pricing


token_emitter = TokenUsageEmitter(
    static_dimensions={"app": "conversation-knowledge-mining"},
    sample_rate=_parse_sample_rate(),
    user_id_hasher=_build_user_id_hasher(),
    pricing=_parse_pricing(),
)

__all__ = ["token_emitter"]
