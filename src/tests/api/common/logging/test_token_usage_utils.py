# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Tests for common.logging.token_usage_utils (token usage extraction and event emission)."""

from __future__ import annotations
from unittest.mock import MagicMock, patch

from common.logging.token_usage_utils import (
    _to_int,
    emit_agent_token_event,
    emit_model_token_event,
    emit_user_token_event,
    emit_team_token_event,
    emit_summary_token_event,
    emit_all_token_events,
    extract_token_usage,
    extract_token_usage_from_stream_chunk,
    extract_token_usage_from_dict,
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


# ── extract_token_usage ────────────────────────────────────────────────

class TestExtractTokenUsage:
    """Token extraction from various response shapes."""

    def test_usage_details_dict_with_standard_keys(self):
        response = MagicMock()
        response.usage_details = {
            "input_token_count": 100,
            "output_token_count": 50,
            "total_token_count": 150,
        }
        result = extract_token_usage(response)
        assert result == {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        }

    def test_usage_details_dict_with_openai_keys(self):
        response = MagicMock()
        response.usage_details = {
            "prompt_tokens": 200,
            "completion_tokens": 80,
            "total_tokens": 280,
        }
        result = extract_token_usage(response)
        assert result == {
            "input_tokens": 200,
            "output_tokens": 80,
            "total_tokens": 280,
        }

    def test_usage_details_prefers_input_output_over_legacy_when_both_present(self):
        response = MagicMock()
        response.usage_details = {
            "input_tokens": 423,
            "output_tokens": 18,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 441,
        }
        result = extract_token_usage(response)
        assert result == {
            "input_tokens": 423,
            "output_tokens": 18,
            "total_tokens": 441,
        }

    def test_usage_details_none_falls_to_usage_attribute(self):
        response = MagicMock()
        response.usage_details = None
        response.usage = {
            "prompt_tokens": 300,
            "completion_tokens": 120,
            "total_tokens": 420,
        }
        response.raw_representation = None
        result = extract_token_usage(response)
        assert result == {
            "input_tokens": 300,
            "output_tokens": 120,
            "total_tokens": 420,
        }

    def test_raw_representation_dict_usage(self):
        response = MagicMock()
        response.usage_details = None
        response.usage = None
        response.raw_representation.usage = {
            "prompt_tokens": 50,
            "completion_tokens": 25,
            "total_tokens": 75,
        }
        result = extract_token_usage(response)
        assert result == {
            "input_tokens": 50,
            "output_tokens": 25,
            "total_tokens": 75,
        }

    def test_usage_details_object_with_attributes(self):
        """Handle UsageDetails object (not dict) from agent framework."""
        response = MagicMock()
        usage_obj = MagicMock()
        usage_obj.input_token_count = 400
        usage_obj.output_token_count = 150
        usage_obj.total_token_count = 550
        response.usage_details = usage_obj
        result = extract_token_usage(response)
        assert result == {
            "input_tokens": 400,
            "output_tokens": 150,
            "total_tokens": 550,
        }

    def test_no_usage_returns_zeros(self):
        response = MagicMock()
        response.usage_details = None
        response.usage = None
        response.raw_representation = None
        result = extract_token_usage(response)
        assert result == {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    def test_total_computed_from_input_output_when_missing(self):
        response = MagicMock()
        response.usage_details = {
            "input_token_count": 100,
            "output_token_count": 50,
        }
        result = extract_token_usage(response)
        assert result["total_tokens"] == 150


# ── extract_token_usage_from_stream_chunk ──────────────────────────────

class TestExtractTokenUsageFromStreamChunk:
    """Token extraction from streaming chunks."""

    def test_chunk_with_usage_details(self):
        chunk = MagicMock()
        chunk.usage_details = {
            "input_token_count": 500,
            "output_token_count": 200,
            "total_token_count": 700,
        }
        result = extract_token_usage_from_stream_chunk(chunk)
        assert result == {
            "input_tokens": 500,
            "output_tokens": 200,
            "total_tokens": 700,
        }

    def test_chunk_without_usage_returns_zeros(self):
        chunk = MagicMock()
        chunk.usage_details = None
        chunk.usage = None
        chunk.raw_representation = None
        chunk.metadata = None
        result = extract_token_usage_from_stream_chunk(chunk)
        assert result == {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }


# ── extract_token_usage_from_dict ──────────────────────────────────────

class TestExtractTokenUsageFromDict:
    """Token extraction from dictionaries."""

    def test_dict_with_prompt_completion_keys(self):
        result = extract_token_usage_from_dict({
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        })
        assert result == {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        }

    def test_dict_with_input_output_keys(self):
        result = extract_token_usage_from_dict({
            "input_tokens": 200,
            "output_tokens": 80,
            "total_tokens": 280,
        })
        assert result == {
            "input_tokens": 200,
            "output_tokens": 80,
            "total_tokens": 280,
        }

    def test_dict_prefers_input_output_over_legacy_when_both_present(self):
        result = extract_token_usage_from_dict({
            "input_tokens": 297,
            "output_tokens": 3870,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 4167,
        })
        assert result == {
            "input_tokens": 297,
            "output_tokens": 3870,
            "total_tokens": 4167,
        }


# ── emit_agent_token_event ─────────────────────────────────────────────

class TestEmitAgentTokenEvent:
    """Custom event emission for per-agent token usage."""

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_emits_correct_event(self, mock_track):
        usage = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        emit_agent_token_event(
            agent_name="orchestrator",
            model_deployment_name="gpt-4o",
            usage=usage,
            conversation_id="conv-123",
            user_id="user-456",
        )
        mock_track.assert_called_once_with("LLM_Agent_Token_Usage", {
            "agent_name": "orchestrator",
            "input_tokens": "100",
            "output_tokens": "50",
            "total_tokens": "150",
            "model_deployment_name": "gpt-4o",
            "conversation_id": "conv-123",
            "user_id": "user-456",
        })


# ── emit_user_token_event ──────────────────────────────────────────────

class TestEmitUserTokenEvent:
    """Custom event emission for per-user token usage."""

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_emits_correct_event(self, mock_track):
        usage = {"input_tokens": 200, "output_tokens": 80, "total_tokens": 280}
        emit_user_token_event(
            user_id="user-789",
            usage=usage,
            agent_name="orchestrator",
            model_deployment_name="gpt-4o",
            conversation_id="conv-123",
        )
        mock_track.assert_called_once_with("LLM_User_Token_Usage", {
            "user_id": "user-789",
            "input_tokens": "200",
            "output_tokens": "80",
            "total_tokens": "280",
            "agent_name": "orchestrator",
            "model_deployment_name": "gpt-4o",
            "conversation_id": "conv-123",
        })


# ── emit_team_token_event ──────────────────────────────────────────────

class TestEmitTeamTokenEvent:
    """Custom event emission for per-team token usage."""

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_emits_correct_event(self, mock_track):
        usage = {"input_tokens": 300, "output_tokens": 120, "total_tokens": 420}
        emit_team_token_event(
            team_name="engineering",
            usage=usage,
            user_id="user-789",
            agent_name="orchestrator",
            model_deployment_name="gpt-4o",
            conversation_id="conv-123",
        )
        mock_track.assert_called_once_with("LLM_Team_Token_Usage", {
            "team_name": "engineering",
            "input_tokens": "300",
            "output_tokens": "120",
            "total_tokens": "420",
            "user_id": "user-789",
            "agent_name": "orchestrator",
            "model_deployment_name": "gpt-4o",
            "conversation_id": "conv-123",
        })


# ── emit_model_token_event ─────────────────────────────────────────────

class TestEmitModelTokenEvent:
    """Custom event emission for per-model token usage."""

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_emits_correct_event(self, mock_track):
        usage = {"input_tokens": 200, "output_tokens": 80, "total_tokens": 280}
        emit_model_token_event(
            model_deployment_name="gpt-4o",
            usage=usage,
            conversation_id="conv-456",
            user_id="user-789",
            agent_name="orchestrator",
        )
        mock_track.assert_called_once_with("LLM_Model_Token_Usage", {
            "model_deployment_name": "gpt-4o",
            "input_tokens": "200",
            "output_tokens": "80",
            "total_tokens": "280",
            "conversation_id": "conv-456",
            "user_id": "user-789",
            "agent_name": "orchestrator",
        })


# ── emit_summary_token_event ──────────────────────────────────────────

class TestEmitSummaryTokenEvent:
    """Custom event emission for conversation-level token summary."""

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_emits_correct_event(self, mock_track):
        emit_summary_token_event(
            total_input_tokens=500,
            total_output_tokens=200,
            total_tokens=700,
            conversation_id="conv-789",
            user_id="user-123",
            team_name="engineering",
            agent_name="orchestrator",
            model_deployment_name="gpt-4o",
        )
        mock_track.assert_called_once_with("LLM_Token_Usage_Summary", {
            "total_input_tokens": "500",
            "total_output_tokens": "200",
            "total_tokens": "700",
            "conversation_id": "conv-789",
            "user_id": "user-123",
            "team_name": "engineering",
            "agent_name": "orchestrator",
            "model_deployment_name": "gpt-4o",
        })


# ── emit_all_token_events ─────────────────────────────────────────────

class TestEmitAllTokenEvents:
    """Convenience function that emits all token tracking events."""

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_emits_all_events_when_tokens_present(self, mock_track):
        usage = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        emit_all_token_events(
            agent_name="orchestrator",
            model_deployment_name="gpt-4o",
            usage=usage,
            conversation_id="conv-123",
            user_id="user-456",
            team_name="engineering",
        )
        # Should emit 5 events: agent, user, team, model, summary
        assert mock_track.call_count == 5
        event_names = [call[0][0] for call in mock_track.call_args_list]
        assert "LLM_Agent_Token_Usage" in event_names
        assert "LLM_User_Token_Usage" in event_names
        assert "LLM_Team_Token_Usage" in event_names
        assert "LLM_Model_Token_Usage" in event_names
        assert "LLM_Token_Usage_Summary" in event_names

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_skips_all_events_when_zero_tokens(self, mock_track):
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        emit_all_token_events(
            agent_name="orchestrator",
            model_deployment_name="gpt-4o",
            usage=usage,
            conversation_id="conv-123",
            user_id="user-456",
        )
        mock_track.assert_not_called()

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_skips_user_event_when_no_user_id(self, mock_track):
        usage = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        emit_all_token_events(
            agent_name="orchestrator",
            model_deployment_name="gpt-4o",
            usage=usage,
            conversation_id="conv-123",
            user_id="",
            team_name="engineering",
        )
        # Should emit 4 events (no user event)
        assert mock_track.call_count == 4
        event_names = [call[0][0] for call in mock_track.call_args_list]
        assert "LLM_User_Token_Usage" not in event_names

    @patch.dict("os.environ", {"TEAM_NAME": "platform-team"})
    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_uses_env_var_for_team_name(self, mock_track):
        usage = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        emit_all_token_events(
            agent_name="orchestrator",
            model_deployment_name="gpt-4o",
            usage=usage,
            conversation_id="conv-123",
            user_id="user-456",
        )
        # Find the team event call
        team_call = next(
            call for call in mock_track.call_args_list
            if call[0][0] == "LLM_Team_Token_Usage"
        )
        assert team_call[0][1]["team_name"] == "platform-team"
