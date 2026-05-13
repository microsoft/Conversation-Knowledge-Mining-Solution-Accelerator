"""Tests for common.logging.token_usage_utils (token extraction and event emission)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

from common.logging.token_usage_utils import (
    _to_int,
    emit_agent_token_event,
    emit_model_token_event,
    emit_session_token_event,
    emit_team_token_event,
    emit_user_token_event,
    emit_summary_token_event,
    extract_token_usage,
    track_all_token_events,
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

    def test_empty_string_returns_default(self):
        assert _to_int("") == 0

    def test_whitespace_string_returns_default(self):
        assert _to_int("  ") == 0


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

    def test_usage_details_none_falls_to_raw_representation(self):
        response = MagicMock()
        response.usage_details = None
        usage_obj = MagicMock()
        usage_obj.prompt_tokens = 300
        usage_obj.completion_tokens = 120
        usage_obj.total_tokens = 420
        usage_obj.input_tokens = 0
        usage_obj.output_tokens = 0
        response.raw_representation.usage = usage_obj
        result = extract_token_usage(response)
        assert result == {
            "input_tokens": 300,
            "output_tokens": 120,
            "total_tokens": 420,
        }

    def test_raw_representation_dict_usage(self):
        response = MagicMock()
        response.usage_details = None
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

    def test_no_usage_returns_zeros(self):
        response = MagicMock()
        response.usage_details = None
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


# ── emit_agent_token_event ─────────────────────────────────────────────


class TestEmitAgentTokenEvent:
    """Custom event emission for per-agent token usage."""

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_emits_correct_event(self, mock_track):
        usage = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        emit_agent_token_event(
            agent_name="ConversationAgent",
            model_deployment_name="gpt-4o",
            usage=usage,
            conversation_id="conv-123",
            user_id="user-456",
        )
        mock_track.assert_called_once_with("LLM_Agent_Token_Usage", {
            "agent_name": "ConversationAgent",
            "input_tokens": "100",
            "output_tokens": "50",
            "total_tokens": "150",
            "model_deployment_name": "gpt-4o",
            "conversation_id": "conv-123",
            "user_id": "user-456",
            "session_id": "",
            "team_id": "",
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
        )
        mock_track.assert_called_once_with("LLM_Model_Token_Usage", {
            "model_deployment_name": "gpt-4o",
            "input_tokens": "200",
            "output_tokens": "80",
            "total_tokens": "280",
            "conversation_id": "conv-456",
            "user_id": "user-789",
            "session_id": "",
            "team_id": "",
        })


# ── emit_user_token_event ─────────────────────────────────────────────


class TestEmitUserTokenEvent:
    """Custom event emission for per-user token usage."""

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_emits_correct_event(self, mock_track):
        usage = {"input_tokens": 150, "output_tokens": 60, "total_tokens": 210}
        emit_user_token_event(
            user_id="user-123",
            agent_name="ConversationAgent",
            model_deployment_name="gpt-4o",
            usage=usage,
            conversation_id="conv-789",
        )
        mock_track.assert_called_once_with("LLM_User_Token_Usage", {
            "user_id": "user-123",
            "agent_name": "ConversationAgent",
            "model_deployment_name": "gpt-4o",
            "input_tokens": "150",
            "output_tokens": "60",
            "total_tokens": "210",
            "conversation_id": "conv-789",
            "session_id": "",
            "team_id": "",
        })


class TestEmitTeamTokenEvent:
    """Custom event emission for per-team token usage."""

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_emits_correct_event(self, mock_track):
        usage = {"input_tokens": 170, "output_tokens": 90, "total_tokens": 260}
        emit_team_token_event(
            team_id="team-001",
            agent_name="ConversationAgent",
            model_deployment_name="gpt-4o",
            usage=usage,
            conversation_id="conv-900",
            user_id="user-222",
            session_id="session-900",
        )
        mock_track.assert_called_once_with("LLM_Team_Token_Usage", {
            "team_id": "team-001",
            "agent_name": "ConversationAgent",
            "model_deployment_name": "gpt-4o",
            "input_tokens": "170",
            "output_tokens": "90",
            "total_tokens": "260",
            "conversation_id": "conv-900",
            "user_id": "user-222",
            "session_id": "session-900",
        })


class TestEmitSessionTokenEvent:
    """Custom event emission for per-session token usage."""

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_emits_correct_event(self, mock_track):
        usage = {"input_tokens": 70, "output_tokens": 30, "total_tokens": 100}
        emit_session_token_event(
            session_id="session-111",
            agent_name="TitleAgent",
            model_deployment_name="gpt-4o-mini",
            usage=usage,
            conversation_id="conv-111",
            user_id="user-333",
            team_id="team-xyz",
        )
        mock_track.assert_called_once_with("LLM_Session_Token_Usage", {
            "session_id": "session-111",
            "agent_name": "TitleAgent",
            "model_deployment_name": "gpt-4o-mini",
            "input_tokens": "70",
            "output_tokens": "30",
            "total_tokens": "100",
            "conversation_id": "conv-111",
            "user_id": "user-333",
            "team_id": "team-xyz",
        })


# ── emit_summary_token_event ──────────────────────────────────────────


class TestEmitSummaryTokenEvent:
    """Custom event emission for token usage summary."""

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_emits_correct_event(self, mock_track):
        emit_summary_token_event(
            total_input_tokens=500,
            total_output_tokens=200,
            total_tokens=700,
            conversation_id="conv-789",
            user_id="user-abc",
            agent_name="ConversationAgent",
            model_deployment_name="gpt-4o",
        )
        mock_track.assert_called_once_with("LLM_Token_Usage_Summary", {
            "total_input_tokens": "500",
            "total_output_tokens": "200",
            "total_tokens": "700",
            "conversation_id": "conv-789",
            "user_id": "user-abc",
            "agent_name": "ConversationAgent",
            "model_deployment_name": "gpt-4o",
            "session_id": "",
            "team_id": "",
        })


# ── track_all_token_events ────────────────────────────────────────────


class TestTrackAllTokenEvents:
    """Convenience function that emits all event types."""

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_emits_all_six_events_with_user_team_session(self, mock_track):
        usage = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        track_all_token_events(
            agent_name="ConversationAgent",
            model_deployment_name="gpt-4o",
            usage=usage,
            conversation_id="conv-1",
            user_id="user-1",
            team_id="team-1",
            session_id="session-1",
        )
        # Should emit 6 events: agent, model, user, team, session, summary
        assert mock_track.call_count == 6
        event_names = [c.args[0] for c in mock_track.call_args_list]
        assert "LLM_Agent_Token_Usage" in event_names
        assert "LLM_Model_Token_Usage" in event_names
        assert "LLM_User_Token_Usage" in event_names
        assert "LLM_Team_Token_Usage" in event_names
        assert "LLM_Session_Token_Usage" in event_names
        assert "LLM_Token_Usage_Summary" in event_names

    @patch("common.logging.token_usage_utils.track_event_if_configured")
    def test_skips_user_event_without_user_id(self, mock_track):
        usage = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        track_all_token_events(
            agent_name="TitleAgent",
            model_deployment_name="gpt-4o-mini",
            usage=usage,
        )
        # Should emit 3 events: agent, model, summary (no user/team/session)
        assert mock_track.call_count == 3
        event_names = [c.args[0] for c in mock_track.call_args_list]
        assert "LLM_User_Token_Usage" not in event_names
        assert "LLM_Team_Token_Usage" not in event_names
        assert "LLM_Session_Token_Usage" not in event_names
