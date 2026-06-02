# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Tests for common.logging.llm_token_telemetry (cross-accelerator token telemetry)."""

from __future__ import annotations

from unittest.mock import MagicMock

from common.logging.llm_token_telemetry import (
    _to_int,
    TokenUsage,
    TokenUsageEmitter,
    TokenUsageScope,
    extract_usage,
    extract_usage_from_dict,
    extract_usage_from_stream_chunk,
    EVENT_AGENT,
    EVENT_MODEL,
    EVENT_SUMMARY,
    EVENT_USER,
    EVENT_TEAM,
)


# ── _to_int helper ─────────────────────────────────────────────────────

class TestToInt:
    """Conversion helper for safely casting token counts."""

    def test_none_returns_default(self):
        assert _to_int(None) == 0

    def test_bool_returns_default(self):
        assert _to_int(True) == 0
        assert _to_int(False) == 0

    def test_int_passthrough(self):
        assert _to_int(42) == 42

    def test_float_truncates(self):
        assert _to_int(3.7) == 3

    def test_digit_string(self):
        assert _to_int("100") == 100

    def test_non_digit_string_returns_default(self):
        assert _to_int("abc") == 0

    def test_custom_default(self):
        assert _to_int(None, default=5) == 5


# ── TokenUsage dataclass ──────────────────────────────────────────────

class TestTokenUsage:
    """TokenUsage dataclass behavior."""

    def test_default_values(self):
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0
        assert not usage.has_any

    def test_has_any_true(self):
        usage = TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15)
        assert usage.has_any

    def test_addition(self):
        a = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        b = TokenUsage(input_tokens=200, output_tokens=80, total_tokens=280)
        result = a + b
        assert result.input_tokens == 300
        assert result.output_tokens == 130
        assert result.total_tokens == 430

    def test_to_event_props(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        props = usage.to_event_props()
        assert props == {
            "input_tokens": "100",
            "output_tokens": "50",
            "total_tokens": "150",
        }


# ── extract_usage ─────────────────────────────────────────────────────

class TestExtractUsage:
    """Token extraction from various response shapes."""

    def test_usage_details_dict_with_standard_keys(self):
        response = MagicMock()
        response.usage_details = {
            "input_token_count": 100,
            "output_token_count": 50,
            "total_token_count": 150,
        }
        result = extract_usage(response)
        assert result == TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)

    def test_usage_details_dict_with_openai_keys(self):
        response = MagicMock()
        response.usage_details = {
            "prompt_tokens": 200,
            "completion_tokens": 80,
            "total_tokens": 280,
        }
        result = extract_usage(response)
        assert result == TokenUsage(input_tokens=200, output_tokens=80, total_tokens=280)

    def test_usage_details_none_falls_to_usage_attribute(self):
        response = MagicMock()
        response.usage_details = None
        response.usage = {
            "prompt_tokens": 300,
            "completion_tokens": 120,
            "total_tokens": 420,
        }
        response.raw_representation = None
        response.messages = None
        result = extract_usage(response)
        assert result == TokenUsage(input_tokens=300, output_tokens=120, total_tokens=420)

    def test_raw_representation_dict_usage(self):
        response = MagicMock()
        response.usage_details = None
        response.usage = None
        response.raw_representation.usage = {
            "prompt_tokens": 50,
            "completion_tokens": 25,
            "total_tokens": 75,
        }
        response.messages = None
        result = extract_usage(response)
        assert result == TokenUsage(input_tokens=50, output_tokens=25, total_tokens=75)

    def test_no_usage_returns_none(self):
        response = MagicMock()
        response.usage_details = None
        response.usage = None
        response.raw_representation = None
        response.messages = None
        result = extract_usage(response)
        assert result is None

    def test_total_computed_from_input_output_when_missing(self):
        response = MagicMock()
        response.usage_details = {
            "input_token_count": 100,
            "output_token_count": 50,
        }
        result = extract_usage(response)
        assert result.total_tokens == 150


# ── extract_usage_from_stream_chunk ───────────────────────────────────

class TestExtractUsageFromStreamChunk:
    """Token extraction from streaming chunks."""

    def test_chunk_with_usage_details(self):
        chunk = MagicMock()
        chunk.usage_details = {
            "input_token_count": 500,
            "output_token_count": 200,
            "total_token_count": 700,
        }
        result = extract_usage_from_stream_chunk(chunk)
        assert result == TokenUsage(input_tokens=500, output_tokens=200, total_tokens=700)

    def test_chunk_without_usage_returns_none(self):
        chunk = MagicMock()
        chunk.usage_details = None
        chunk.usage = None
        chunk.raw_representation = None
        chunk.messages = None
        chunk.metadata = None
        result = extract_usage_from_stream_chunk(chunk)
        assert result is None


# ── extract_usage_from_dict ───────────────────────────────────────────

class TestExtractUsageFromDict:
    """Token extraction from dictionaries."""

    def test_dict_with_prompt_completion_keys(self):
        result = extract_usage_from_dict({
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        })
        assert result == TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)

    def test_dict_with_input_output_keys(self):
        result = extract_usage_from_dict({
            "input_tokens": 200,
            "output_tokens": 80,
            "total_tokens": 280,
        })
        assert result == TokenUsage(input_tokens=200, output_tokens=80, total_tokens=280)

    def test_none_returns_none(self):
        result = extract_usage_from_dict(None)
        assert result is None


# ── TokenUsageEmitter ─────────────────────────────────────────────────

class TestTokenUsageEmitter:
    """Emitter emit_all behavior."""

    def test_emit_all_calls_sink(self):
        sink = MagicMock()
        emitter = TokenUsageEmitter(
            connection_string="InstrumentationKey=test",
            event_sink=sink,
        )
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        emitter.emit_all(
            agent_name="orchestrator",
            model_deployment_name="gpt-4o",
            usage=usage,
            conversation_id="conv-123",
            user_id="user-456",
        )
        # Should have emitted: agent, model, summary (at minimum)
        event_names = [call[0][0] for call in sink.call_args_list]
        assert EVENT_AGENT in event_names
        assert EVENT_MODEL in event_names
        assert EVENT_SUMMARY in event_names

    def test_emit_all_with_user_and_team(self):
        sink = MagicMock()
        emitter = TokenUsageEmitter(
            connection_string="InstrumentationKey=test",
            event_sink=sink,
        )
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        emitter.emit_all(
            agent_name="orchestrator",
            model_deployment_name="gpt-4o",
            usage=usage,
            emit_user_event=True,
            emit_team_event=True,
            user_id="user-789",
            team_name="engineering",
        )
        event_names = [call[0][0] for call in sink.call_args_list]
        assert EVENT_USER in event_names
        assert EVENT_TEAM in event_names

    def test_no_emit_when_no_tokens(self):
        sink = MagicMock()
        emitter = TokenUsageEmitter(
            connection_string="InstrumentationKey=test",
            event_sink=sink,
        )
        usage = TokenUsage()
        emitter.emit_all(
            agent_name="orchestrator",
            model_deployment_name="gpt-4o",
            usage=usage,
        )
        sink.assert_not_called()

    def test_not_enabled_without_connection_string(self):
        emitter = TokenUsageEmitter(connection_string=None, event_sink=MagicMock())
        # When no connection string, enabled is False
        assert not emitter.enabled


# ── TokenUsageScope ───────────────────────────────────────────────────

class TestTokenUsageScope:
    """Scope context manager behavior."""

    def test_scope_accumulates_and_emits(self):
        sink = MagicMock()
        emitter = TokenUsageEmitter(
            connection_string="InstrumentationKey=test",
            event_sink=sink,
        )
        chunk = MagicMock()
        chunk.usage_details = {
            "input_token_count": 200,
            "output_token_count": 100,
            "total_token_count": 300,
        }
        chunk.messages = None

        with TokenUsageScope(
            emitter,
            agent_name="orchestrator",
            model_deployment_name="gpt-4o",
            conversation_id="conv-1",
        ) as scope:
            scope.add(chunk)

        # After exit, events should have been emitted
        assert sink.call_count > 0
        assert scope.usage.total_tokens == 300

    def test_scope_no_emit_when_no_usage(self):
        sink = MagicMock()
        emitter = TokenUsageEmitter(
            connection_string="InstrumentationKey=test",
            event_sink=sink,
        )

        with TokenUsageScope(
            emitter,
            agent_name="orchestrator",
            model_deployment_name="gpt-4o",
        ) as scope:
            pass  # No usage added

        sink.assert_not_called()
        assert not scope.usage.has_any
