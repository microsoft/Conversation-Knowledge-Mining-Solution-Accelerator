# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Cross-accelerator LLM token-usage telemetry helpers.

A single, dependency-light helper module that can be dropped into any Microsoft
Solution Accelerator to capture LLM token usage and emit standardized custom
events to Application Insights.

Public API
----------
- ``TokenUsage``                      -- immutable dataclass for counts
- ``extract_usage(obj)``              -- agent_framework run result / message
- ``extract_usage_from_dict(d)``      -- raw dict from any SDK
- ``extract_usage_from_stream_chunk`` -- streaming chunks
- ``extract_realtime_usage(resp)``    -- Azure AI Voice Live response.done
- ``TokenUsageEmitter``               -- emits the three events + optional
                                         per-user / per-team / speech events
- ``TokenUsageScope``                 -- context-manager that accumulates and
                                         auto-emits on exit
- ``track_tokens``                    -- decorator wrapper around the scope

Design rules
------------
* Telemetry NEVER raises. Extraction failures return ``None``; emission
  failures are logged at WARNING.
* No hard dependency on ``azure-monitor-events-extension``; if absent the
  emitter degrades to logging only.
* Arbitrary correlation dimensions are passed as ``**dimensions`` kwargs and
  surface verbatim as custom-event properties.
"""
from __future__ import annotations

import asyncio
import functools
import logging
import os
import random
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Optional
from unittest.mock import NonCallableMock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event-name constants -- keep these stable; KQL queries and workbooks bind
# to these exact strings.
# ---------------------------------------------------------------------------
EVENT_SUMMARY = "LLM_Token_Usage_Summary"
EVENT_AGENT = "LLM_Agent_Token_Usage"
EVENT_MODEL = "LLM_Model_Token_Usage"
EVENT_USER = "LLM_User_Token_Usage"
EVENT_TEAM = "LLM_Team_Token_Usage"
EVENT_SPEECH = "Speech_Usage"


# Token-count field aliases observed across model providers / SDK versions.
_INPUT_KEYS = (
    "input_token_count",
    "input_tokens",
    "prompt_tokens",
    "promptTokens",
)
_OUTPUT_KEYS = (
    "output_token_count",
    "output_tokens",
    "completion_tokens",
    "completionTokens",
)
_TOTAL_KEYS = (
    "total_token_count",
    "total_tokens",
    "totalTokens",
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TokenUsage:
    """Normalized token-usage record."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Optional realtime / voice fields (None unless populated)
    input_audio_tokens: Optional[int] = None
    input_text_tokens: Optional[int] = None
    input_cached_tokens: Optional[int] = None
    output_audio_tokens: Optional[int] = None
    output_text_tokens: Optional[int] = None

    @property
    def has_any(self) -> bool:
        return bool(self.input_tokens or self.output_tokens or self.total_tokens)

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        if not isinstance(other, TokenUsage):
            return NotImplemented

        def _sum(a: Optional[int], b: Optional[int]) -> Optional[int]:
            if a is None and b is None:
                return None
            return (a or 0) + (b or 0)

        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            input_audio_tokens=_sum(self.input_audio_tokens, other.input_audio_tokens),
            input_text_tokens=_sum(self.input_text_tokens, other.input_text_tokens),
            input_cached_tokens=_sum(self.input_cached_tokens, other.input_cached_tokens),
            output_audio_tokens=_sum(self.output_audio_tokens, other.output_audio_tokens),
            output_text_tokens=_sum(self.output_text_tokens, other.output_text_tokens),
        )

    def to_event_props(self) -> dict[str, str]:
        """Stringified property bag suitable for App Insights custom events."""
        props: dict[str, str] = {
            "input_tokens": str(self.input_tokens),
            "output_tokens": str(self.output_tokens),
            "total_tokens": str(self.total_tokens),
        }
        for name in (
            "input_audio_tokens",
            "input_text_tokens",
            "input_cached_tokens",
            "output_audio_tokens",
            "output_text_tokens",
        ):
            value = getattr(self, name)
            if value is not None:
                props[name] = str(value)
        return props


# ---------------------------------------------------------------------------
# Low-level coercion helpers
# ---------------------------------------------------------------------------
def _to_int(value: Any, default: int = 0) -> int:
    """Best-effort int conversion; bool excluded; never raises."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            return int(s)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Read an attribute or dict key uniformly."""
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _is_iterable(obj: Any) -> bool:
    """True for real iterables (lists/tuples/sets/generators) and objects
    exposing ``__iter__``, but NOT for strings, bytes, or mappings."""
    if obj is None:
        return False
    if isinstance(obj, (list, tuple, set, frozenset)):
        return True
    if isinstance(obj, (str, bytes, bytearray, Mapping)):
        return False
    if isinstance(obj, NonCallableMock):
        return False
    return hasattr(obj, "__iter__")


def _read_counts(usage_obj: Any) -> Optional[TokenUsage]:
    """Read ``input/output/total`` from any usage-bearing object/dict."""
    if usage_obj is None:
        return None

    inp = out = tot = 0
    for k in _INPUT_KEYS:
        v = _get(usage_obj, k)
        if v:
            inp = _to_int(v)
            break
    for k in _OUTPUT_KEYS:
        v = _get(usage_obj, k)
        if v:
            out = _to_int(v)
            break
    for k in _TOTAL_KEYS:
        v = _get(usage_obj, k)
        if v:
            tot = _to_int(v)
            break

    if tot == 0 and (inp or out):
        tot = inp + out
    if not (inp or out or tot):
        return None
    return TokenUsage(input_tokens=inp, output_tokens=out, total_tokens=tot)


# ---------------------------------------------------------------------------
# Extraction -- public
# ---------------------------------------------------------------------------
def extract_usage(result: Any) -> Optional[TokenUsage]:
    """Extract usage from an agent_framework run result, ChatMessage, or
    OpenAI-style ChatCompletion.

    Checks (in order):
      1. ``result.usage_details`` or ``result.usage``
      2. ``result.raw_representation.usage`` (OpenAI ChatCompletion shape)
      3. Aggregated ``result.messages[*].contents[*].usage_details``

    Never raises -- returns ``None`` on any unexpected shape.
    """
    if result is None:
        return None

    try:
        for attr in ("usage_details", "usage"):
            found = _read_counts(_get(result, attr))
            if found:
                return found

        raw = _get(result, "raw_representation")
        if raw is not None:
            found = _read_counts(_get(raw, "usage"))
            if found:
                return found

        aggregated = TokenUsage()
        found_any = False
        messages = _get(result, "messages")
        if not _is_iterable(messages):
            return None
        for msg in messages:
            contents = _get(msg, "contents")
            if not _is_iterable(contents):
                continue
            for content in contents:
                usage = _get(content, "usage_details") or _get(content, "usage")
                piece = _read_counts(usage)
                if piece:
                    aggregated = aggregated + piece
                    found_any = True
        return aggregated if found_any else None
    except Exception as exc:
        logger.debug("extract_usage failed: %s", exc, exc_info=True)
        return None


def extract_usage_from_dict(data: Any) -> Optional[TokenUsage]:
    """Extract from a raw dict / SDK usage object."""
    return _read_counts(data)


def extract_usage_from_stream_chunk(chunk: Any) -> Optional[TokenUsage]:
    """Streaming chunks: try the top-level shape, then ``chunk.metadata.usage``."""
    found = extract_usage(chunk)
    if found:
        return found
    metadata = _get(chunk, "metadata")
    if metadata is not None:
        return _read_counts(_get(metadata, "usage"))
    return None


def extract_realtime_usage(response_obj: Any) -> Optional[TokenUsage]:
    """Azure AI Voice Live ``response.done`` payload extractor.

    Includes audio / text / cached sub-counts when present.
    """
    usage = _get(response_obj, "usage")
    if usage is None:
        return None

    inp = _to_int(_get(usage, "input_tokens"))
    out = _to_int(_get(usage, "output_tokens"))
    tot = _to_int(_get(usage, "total_tokens"))
    if tot == 0 and (inp or out):
        tot = inp + out

    in_details = _get(usage, "input_token_details") or {}
    out_details = _get(usage, "output_token_details") or {}

    def _opt_int(val: Any) -> Optional[int]:
        """Return int if value is present, None otherwise (preserves Optional semantics)."""
        if val is None:
            return None
        return _to_int(val)

    record = TokenUsage(
        input_tokens=inp,
        output_tokens=out,
        total_tokens=tot,
        input_audio_tokens=_opt_int(_get(in_details, "audio_tokens")),
        input_text_tokens=_opt_int(_get(in_details, "text_tokens")),
        input_cached_tokens=_opt_int(_get(in_details, "cached_tokens")),
        output_audio_tokens=_opt_int(_get(out_details, "audio_tokens")),
        output_text_tokens=_opt_int(_get(out_details, "text_tokens")),
    )
    if record.has_any or any(
        v for v in (
            record.input_audio_tokens,
            record.input_text_tokens,
            record.input_cached_tokens,
            record.output_audio_tokens,
            record.output_text_tokens,
        )
    ):
        return record
    return None


# ---------------------------------------------------------------------------
# Tool / sub-agent attribution
# ---------------------------------------------------------------------------
def detect_invoked_tools(result: Any) -> set[str]:
    """Return the set of tool/function names invoked in an agent result."""
    invoked: set[str] = set()
    try:
        messages = _get(result, "messages")
        if not _is_iterable(messages):
            return invoked
        for msg in messages:
            contents = _get(msg, "contents")
            if not _is_iterable(contents):
                continue
            for content in contents:
                if _get(content, "type") == "function_call":
                    name = _get(content, "name")
                    if name:
                        invoked.add(str(name))
    except Exception as exc:
        logger.debug("detect_invoked_tools failed: %s", exc, exc_info=True)
    return invoked


# ---------------------------------------------------------------------------
# Event sink (optional Application Insights dependency)
# ---------------------------------------------------------------------------
EventSink = Callable[[str, Mapping[str, str]], None]


def _default_event_sink() -> Optional[EventSink]:
    """Return ``azure.monitor.events.extension.track_event`` if importable,
    else ``None``."""
    try:
        from azure.monitor.events.extension import track_event  # type: ignore
    except Exception:
        return None
    return track_event


# ---------------------------------------------------------------------------
# Emitter
# ---------------------------------------------------------------------------
class TokenUsageEmitter:
    """Emit standardized token-usage custom events.

    Parameters
    ----------
    connection_string:
        Application Insights connection string. If ``None`` (default), the
        ``APPLICATIONINSIGHTS_CONNECTION_STRING`` env var is consulted.
    static_dimensions:
        Properties merged into every event (e.g. ``{"app": "ckm"}``).
    event_sink:
        Callable ``(event_name, props_dict) -> None``. Override in tests.
    pricing:
        Optional mapping ``{model_deployment_name -> (usd_per_1k_input,
        usd_per_1k_output)}``.
    user_id_hasher:
        Optional callable ``str -> str`` applied to any ``user_id`` value.
    sample_rate:
        Fraction of high-cardinality events shipped, in ``[0.0, 1.0]``.
        The summary event always fires regardless of sample_rate.
    """

    def __init__(
        self,
        *,
        connection_string: Optional[str] = None,
        static_dimensions: Optional[Mapping[str, Any]] = None,
        event_sink: Optional[EventSink] = None,
        pricing: Optional[Mapping[str, tuple[float, float]]] = None,
        user_id_hasher: Optional[Callable[[str], str]] = None,
        sample_rate: float = 1.0,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._cs = connection_string if connection_string is not None else os.getenv(
            "APPLICATIONINSIGHTS_CONNECTION_STRING"
        )
        self._sink = event_sink if event_sink is not None else _default_event_sink()
        self._log = logger or logging.getLogger(__name__)

        self._user_id_hasher = user_id_hasher

        try:
            sr = float(sample_rate)
        except (TypeError, ValueError):
            sr = 1.0
        self._sample_rate = max(0.0, min(1.0, sr))

        self._pricing: dict[str, tuple[float, float]] = {}
        for model, rates in (pricing or {}).items():
            if not model or rates is None:
                continue
            try:
                inp, out = rates
                self._pricing[str(model).lower()] = (float(inp), float(out))
            except (TypeError, ValueError):
                self._log.warning("Ignoring malformed pricing entry: %s=%r", model, rates)

        raw_static = dict(static_dimensions or {})
        if "user_id" in raw_static:
            raw_static["user_id"] = self._apply_user_id_hash(raw_static["user_id"])
        self._static: dict[str, str] = {
            k: ("" if v is None else str(v)) for k, v in raw_static.items()
        }

        self._perf_total_ns: int = 0
        self._perf_emit_count: int = 0
        self._perf_max_ns: int = 0
        self.perf_slow_emit_threshold_ms: float = 50.0

    @property
    def enabled(self) -> bool:
        return bool(self._cs) and self._sink is not None

    @property
    def sample_rate(self) -> float:
        return self._sample_rate

    def _apply_user_id_hash(self, value: Any) -> Any:
        if value is None or value == "" or self._user_id_hasher is None:
            return value
        try:
            return self._user_id_hasher(str(value))
        except Exception as exc:
            self._log.warning("user_id_hasher raised: %s", exc)
            return value

    def _should_sample(self) -> bool:
        if self._sample_rate >= 1.0:
            return True
        if self._sample_rate <= 0.0:
            return False
        return random.random() < self._sample_rate

    def _cost_props(
        self, model_deployment_name: Optional[str], usage: TokenUsage
    ) -> dict[str, str]:
        if not self._pricing or not model_deployment_name:
            return {}
        rate = self._pricing.get(model_deployment_name.lower())
        if not rate:
            return {}
        inp_rate, out_rate = rate
        cost = (usage.input_tokens * inp_rate + usage.output_tokens * out_rate) / 1000.0
        return {"estimated_cost_usd": f"{cost:.6f}"}

    def _summary_cost_props(
        self,
        primary_model: Optional[str],
        additional_agents: Mapping[str, str],
        usage: TokenUsage,
    ) -> dict[str, str]:
        if primary_model:
            cost = self._cost_props(primary_model, usage)
            if cost:
                return cost
        for m in additional_agents.values():
            cost = self._cost_props(m, usage)
            if cost:
                return cost
        return {}

    def emit(self, event_name: str, **dimensions: Any) -> None:
        """Low-level: emit an event with arbitrary properties. Never raises."""
        start_ns = time.perf_counter_ns()
        try:
            props = dict(self._static)
            for k, v in dimensions.items():
                if v is None:
                    continue
                if k == "user_id":
                    v = self._apply_user_id_hash(v)
                    if v is None or v == "":
                        continue
                props[k] = v if isinstance(v, str) else str(v)

            if not self.enabled:
                self._log.debug(
                    "App Insights not configured -- skipping event %s (%s)",
                    event_name, props,
                )
                return
            try:
                self._sink(event_name, props)  # type: ignore[misc]
            except Exception as exc:
                self._log.warning("track_event(%s) failed: %s", event_name, exc)
        finally:
            elapsed_ns = time.perf_counter_ns() - start_ns
            self._perf_total_ns += elapsed_ns
            self._perf_emit_count += 1
            if elapsed_ns > self._perf_max_ns:
                self._perf_max_ns = elapsed_ns
            elapsed_ms = elapsed_ns / 1_000_000.0
            if elapsed_ms > self.perf_slow_emit_threshold_ms:
                self._log.warning(
                    "Token telemetry emit slow: event=%s duration_ms=%.3f",
                    event_name, elapsed_ms,
                )

    def perf_stats(self) -> dict[str, float]:
        """Return cumulative telemetry-overhead stats."""
        count = self._perf_emit_count
        total_ms = self._perf_total_ns / 1_000_000.0
        return {
            "emit_count": float(count),
            "total_ms": total_ms,
            "avg_ms": (total_ms / count) if count else 0.0,
            "max_ms": self._perf_max_ns / 1_000_000.0,
        }

    def reset_perf_stats(self) -> None:
        self._perf_total_ns = 0
        self._perf_emit_count = 0
        self._perf_max_ns = 0

    # -- typed convenience emitters --------------------------------------
    def emit_agent(
        self,
        *,
        agent_name: str,
        model_deployment_name: str,
        usage: TokenUsage,
        **dimensions: Any,
    ) -> None:
        if not usage.has_any or not self._should_sample():
            return
        self.emit(
            EVENT_AGENT,
            agent_name=agent_name,
            model_deployment_name=model_deployment_name,
            **usage.to_event_props(),
            **self._cost_props(model_deployment_name, usage),
            **dimensions,
        )

    def emit_model(
        self,
        *,
        model_deployment_name: str,
        usage: TokenUsage,
        **dimensions: Any,
    ) -> None:
        if not usage.has_any or not self._should_sample():
            return
        self.emit(
            EVENT_MODEL,
            model_deployment_name=model_deployment_name,
            **usage.to_event_props(),
            **self._cost_props(model_deployment_name, usage),
            **dimensions,
        )

    def emit_user(
        self,
        *,
        user_id: str,
        usage: TokenUsage,
        **dimensions: Any,
    ) -> None:
        if not usage.has_any or not user_id or not self._should_sample():
            return
        self.emit(
            EVENT_USER,
            user_id=user_id,
            **usage.to_event_props(),
            **dimensions,
        )

    def emit_team(
        self,
        *,
        team_name: str,
        usage: TokenUsage,
        **dimensions: Any,
    ) -> None:
        if not usage.has_any or not team_name or not self._should_sample():
            return
        self.emit(
            EVENT_TEAM,
            team_name=team_name,
            **usage.to_event_props(),
            **dimensions,
        )

    def emit_summary(
        self,
        *,
        usage: TokenUsage,
        agent_count: int = 1,
        model_count: int = 1,
        primary_model: Optional[str] = None,
        additional_agents: Optional[Mapping[str, str]] = None,
        **dimensions: Any,
    ) -> None:
        """The summary event always fires (ignores ``sample_rate``)."""
        if not usage.has_any:
            return
        props = {
            "total_input_tokens": str(usage.input_tokens),
            "total_output_tokens": str(usage.output_tokens),
            "total_tokens": str(usage.total_tokens),
            "agent_count": str(agent_count),
            "model_count": str(model_count),
            "sample_rate": f"{self._sample_rate:.4f}",
        }
        for k, v in usage.to_event_props().items():
            props.setdefault(k, v)
        props.update(self._summary_cost_props(primary_model, additional_agents or {}, usage))
        self.emit(EVENT_SUMMARY, **props, **dimensions)

    def emit_speech(
        self,
        *,
        model_deployment_name: str,
        source: str,
        usage: TokenUsage,
        **dimensions: Any,
    ) -> None:
        """Voice-Live / realtime speech usage event."""
        if not self._should_sample():
            return
        self.emit(
            EVENT_SPEECH,
            model_deployment_name=model_deployment_name,
            source=source,
            **usage.to_event_props(),
            **self._cost_props(model_deployment_name, usage),
            **dimensions,
        )

    def emit_all(
        self,
        *,
        agent_name: str,
        model_deployment_name: str,
        usage: TokenUsage,
        additional_agents: Optional[Mapping[str, str]] = None,
        emit_user_event: bool = False,
        emit_team_event: bool = False,
        **dimensions: Any,
    ) -> None:
        """Convenience: emit summary, agent, and model events in one shot."""
        if not usage.has_any:
            return

        agents = {agent_name: model_deployment_name}
        if additional_agents:
            agents.update({k: v for k, v in additional_agents.items() if k})
        models = {m for m in agents.values() if m}

        batch_start_ns = time.perf_counter_ns()

        self.emit_agent(
            agent_name=agent_name,
            model_deployment_name=model_deployment_name,
            usage=usage,
            **dimensions,
        )
        for model in models:
            self.emit_model(
                model_deployment_name=model,
                usage=usage,
                **dimensions,
            )
        if emit_user_event and dimensions.get("user_id"):
            self.emit_user(
                user_id=str(dimensions["user_id"]),
                usage=usage,
                agent_name=agent_name,
                model_deployment_name=model_deployment_name,
            )
        if emit_team_event and dimensions.get("team_name"):
            self.emit_team(
                team_name=str(dimensions["team_name"]),
                usage=usage,
                agent_name=agent_name,
                model_deployment_name=model_deployment_name,
            )

        batch_overhead_ms = (time.perf_counter_ns() - batch_start_ns) / 1_000_000.0
        self.emit_summary(
            usage=usage,
            agent_count=len(agents),
            model_count=len(models) or 1,
            primary_model=model_deployment_name,
            additional_agents=additional_agents,
            telemetry_overhead_ms=f"{batch_overhead_ms:.3f}",
            **dimensions,
        )

        safe_dims = dict(dimensions)
        if "user_id" in safe_dims:
            if self._user_id_hasher is not None:
                safe_dims["user_id"] = self._apply_user_id_hash(safe_dims["user_id"])
            else:
                safe_dims.pop("user_id", None)

        self._log.info(
            "[TOKEN USAGE] agent=%s model=%s input=%d output=%d total=%d %s",
            agent_name,
            model_deployment_name,
            usage.input_tokens,
            usage.output_tokens,
            usage.total_tokens,
            " ".join(f"{k}={v}" for k, v in safe_dims.items() if v),
        )


# ---------------------------------------------------------------------------
# Scope / decorator sugar
# ---------------------------------------------------------------------------
@dataclass
class TokenUsageScope(AbstractContextManager):
    """Accumulate usage across multiple results, then emit on exit.

    Example::

        with TokenUsageScope(emitter,
                             agent_name="chat",
                             model_deployment_name=cfg.model,
                             user_id=user_id) as scope:
            result = await agent.run(prompt)
            scope.add(result)
    """

    emitter: TokenUsageEmitter
    agent_name: str
    model_deployment_name: str
    dimensions: dict[str, Any] = field(default_factory=dict)
    additional_agents: dict[str, str] = field(default_factory=dict)
    emit_user_event: bool = False
    emit_team_event: bool = False
    usage: TokenUsage = field(default_factory=TokenUsage)

    def __init__(
        self,
        emitter: TokenUsageEmitter,
        *,
        agent_name: str,
        model_deployment_name: str,
        additional_agents: Optional[Mapping[str, str]] = None,
        emit_user_event: bool = False,
        emit_team_event: bool = False,
        **dimensions: Any,
    ) -> None:
        self.emitter = emitter
        self.agent_name = agent_name
        self.model_deployment_name = model_deployment_name
        self.additional_agents = dict(additional_agents or {})
        self.emit_user_event = emit_user_event
        self.emit_team_event = emit_team_event
        self.dimensions = dict(dimensions)
        self.usage = TokenUsage()
        self._extract_ns: int = 0
        self._emit_ns: int = 0

    def add(self, source: Any) -> Optional[TokenUsage]:
        """Extract usage from any supported shape and add to the running total."""
        start_ns = time.perf_counter_ns()
        try:
            found = extract_usage_from_stream_chunk(source)
        except Exception as exc:
            logger.debug("TokenUsageScope.add failed: %s", exc, exc_info=True)
            return None
        finally:
            self._extract_ns += time.perf_counter_ns() - start_ns
        if found:
            self.usage = self.usage + found
        return found

    def add_usage(self, usage: TokenUsage) -> None:
        self.usage = self.usage + usage

    def add_chunks(self, chunks: Iterable[Any]) -> None:
        for c in chunks:
            self.add(c)

    @property
    def extract_ms(self) -> float:
        return self._extract_ns / 1_000_000.0

    @property
    def emit_ms(self) -> float:
        return self._emit_ns / 1_000_000.0

    @property
    def total_overhead_ms(self) -> float:
        return self.extract_ms + self.emit_ms

    def __exit__(self, exc_type, exc, tb) -> None:
        emit_start_ns = time.perf_counter_ns()
        try:
            self.emitter.emit_all(
                agent_name=self.agent_name,
                model_deployment_name=self.model_deployment_name,
                usage=self.usage,
                additional_agents=self.additional_agents,
                emit_user_event=self.emit_user_event,
                emit_team_event=self.emit_team_event,
                **self.dimensions,
            )
        except Exception as emit_exc:
            logger.warning("TokenUsageScope emit failed: %s", emit_exc)
        finally:
            self._emit_ns += time.perf_counter_ns() - emit_start_ns
            logger.debug(
                "TokenUsageScope overhead: agent=%s extract_ms=%.3f "
                "emit_ms=%.3f total_ms=%.3f",
                self.agent_name,
                self.extract_ms,
                self.emit_ms,
                self.total_overhead_ms,
            )
        return None


def track_tokens(
    emitter: TokenUsageEmitter,
    *,
    agent_name: str,
    model_deployment_name: str,
    dimension_args: Optional[Mapping[str, str]] = None,
    additional_agents: Optional[Mapping[str, str]] = None,
    emit_user_event: bool = False,
    emit_team_event: bool = False,
):
    """Decorator: wrap an async or sync function that returns an LLM result."""

    dim_args = dict(dimension_args or {})

    def _decorator(fn: Callable[..., Any]):
        is_coro = asyncio.iscoroutinefunction(fn)

        if is_coro:
            @functools.wraps(fn)
            async def _aw(*args, **kwargs) -> Any:
                with _scope_for(kwargs) as scope:
                    result = await fn(*args, **kwargs)
                    scope.add(result)
                    return result
            return _aw

        @functools.wraps(fn)
        def _sw(*args, **kwargs) -> Any:
            with _scope_for(kwargs) as scope:
                result = fn(*args, **kwargs)
                scope.add(result)
                return result
        return _sw

    def _scope_for(call_kwargs: Mapping[str, Any]) -> TokenUsageScope:
        dimensions = {
            prop: call_kwargs.get(kw)
            for prop, kw in dim_args.items()
            if call_kwargs.get(kw) is not None
        }
        return TokenUsageScope(
            emitter,
            agent_name=agent_name,
            model_deployment_name=model_deployment_name,
            additional_agents=additional_agents,
            emit_user_event=emit_user_event,
            emit_team_event=emit_team_event,
            **dimensions,
        )

    return _decorator


__all__ = [
    "EVENT_SUMMARY",
    "EVENT_AGENT",
    "EVENT_MODEL",
    "EVENT_USER",
    "EVENT_TEAM",
    "EVENT_SPEECH",
    "TokenUsage",
    "TokenUsageEmitter",
    "TokenUsageScope",
    "track_tokens",
    "extract_usage",
    "extract_usage_from_dict",
    "extract_usage_from_stream_chunk",
    "extract_realtime_usage",
    "detect_invoked_tools",
]
