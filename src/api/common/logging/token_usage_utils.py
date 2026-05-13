"""Token usage tracking for LLM calls in the Conversation Knowledge Mining pipeline.

Extracts token counts from Azure OpenAI agent framework responses and emits
custom events to Application Insights for monitoring, cost estimation, and
performance optimization.

Tracking dimensions:
- Per Agent: ConversationAgent, TitleAgent
- Per Model: Azure OpenAI deployment name
- Per User: user_principal_id from EasyAuth headers
- Per Team: team_id derived from tenant/identity context
- Per Session: session_id aligned with conversation_id
"""

import logging
from typing import Any

from common.logging.event_utils import track_event_if_configured

logger = logging.getLogger(__name__)


def extract_token_usage(response: Any) -> dict[str, int]:
    """Extract token usage from an agent framework response.

    Checks multiple attribute paths to handle different response shapes
    from the agent framework SDK.

    Args:
        response: The response object from agent.run().

    Returns:
        Dict with keys: input_tokens, output_tokens, total_tokens.
        All default to 0 if not found.
    """
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0

    # Path 1: usage_details attribute (set by agent framework SDK)
    usage_details = getattr(response, "usage_details", None)
    if isinstance(usage_details, dict):
        input_tokens = _to_int(
            usage_details.get("input_token_count")
            or usage_details.get("prompt_tokens")
            or usage_details.get("input_tokens")
        )
        output_tokens = _to_int(
            usage_details.get("output_token_count")
            or usage_details.get("completion_tokens")
            or usage_details.get("output_tokens")
        )
        total_tokens = _to_int(
            usage_details.get("total_token_count")
            or usage_details.get("total_tokens")
        ) or (input_tokens + output_tokens)

    # Path 2: raw_representation.usage (raw Azure OpenAI response)
    if total_tokens == 0:
        raw = getattr(response, "raw_representation", None)
        if raw is not None:
            usage_obj = getattr(raw, "usage", None)
            if usage_obj is not None:
                if isinstance(usage_obj, dict):
                    input_tokens = _to_int(
                        usage_obj.get("prompt_tokens")
                        or usage_obj.get("input_tokens")
                    )
                    output_tokens = _to_int(
                        usage_obj.get("completion_tokens")
                        or usage_obj.get("output_tokens")
                    )
                    total_tokens = _to_int(
                        usage_obj.get("total_tokens")
                    ) or (input_tokens + output_tokens)
                else:
                    input_tokens = _to_int(
                        getattr(usage_obj, "prompt_tokens", 0)
                        or getattr(usage_obj, "input_tokens", 0)
                    )
                    output_tokens = _to_int(
                        getattr(usage_obj, "completion_tokens", 0)
                        or getattr(usage_obj, "output_tokens", 0)
                    )
                    total_tokens = _to_int(
                        getattr(usage_obj, "total_tokens", 0)
                    ) or (input_tokens + output_tokens)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def emit_agent_token_event(
    agent_name: str,
    model_deployment_name: str,
    usage: dict[str, int],
    conversation_id: str = "",
    user_id: str = "",
    session_id: str = "",
    team_id: str = "",
) -> None:
    """Emit a per-agent token usage event to Application Insights.

    Args:
        agent_name: Name of the agent (e.g. 'ConversationAgent', 'TitleAgent').
        model_deployment_name: Azure OpenAI model deployment name.
        usage: Dict with input_tokens, output_tokens, total_tokens.
        conversation_id: Conversation ID for correlation.
        user_id: Authenticated user's principal ID.
        session_id: Session ID for per-session analysis.
        team_id: Team identifier (tenant or group based).
    """
    track_event_if_configured("LLM_Agent_Token_Usage", {
        "agent_name": agent_name,
        "input_tokens": str(usage.get("input_tokens", 0)),
        "output_tokens": str(usage.get("output_tokens", 0)),
        "total_tokens": str(usage.get("total_tokens", 0)),
        "model_deployment_name": model_deployment_name,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "session_id": session_id,
        "team_id": team_id,
    })
    logger.info(
        "[TOKEN USAGE] agent=%s model=%s input=%d output=%d total=%d user=%s conversation=%s",
        agent_name,
        model_deployment_name,
        usage.get("input_tokens", 0),
        usage.get("output_tokens", 0),
        usage.get("total_tokens", 0),
        user_id,
        conversation_id,
    )


def emit_model_token_event(
    model_deployment_name: str,
    usage: dict[str, int],
    conversation_id: str = "",
    user_id: str = "",
    session_id: str = "",
    team_id: str = "",
) -> None:
    """Emit a per-model token usage event to Application Insights.

    Args:
        model_deployment_name: Azure OpenAI model deployment name.
        usage: Dict with input_tokens, output_tokens, total_tokens.
        conversation_id: Conversation ID for correlation.
        user_id: Authenticated user's principal ID.
        session_id: Session ID for per-session analysis.
        team_id: Team identifier (tenant or group based).
    """
    track_event_if_configured("LLM_Model_Token_Usage", {
        "model_deployment_name": model_deployment_name,
        "input_tokens": str(usage.get("input_tokens", 0)),
        "output_tokens": str(usage.get("output_tokens", 0)),
        "total_tokens": str(usage.get("total_tokens", 0)),
        "conversation_id": conversation_id,
        "user_id": user_id,
        "session_id": session_id,
        "team_id": team_id,
    })


def emit_user_token_event(
    user_id: str,
    agent_name: str,
    model_deployment_name: str,
    usage: dict[str, int],
    conversation_id: str = "",
    session_id: str = "",
    team_id: str = "",
) -> None:
    """Emit a per-user token usage event to Application Insights.

    Args:
        user_id: Authenticated user's principal ID.
        agent_name: Name of the agent invoked.
        model_deployment_name: Azure OpenAI model deployment name.
        usage: Dict with input_tokens, output_tokens, total_tokens.
        conversation_id: Conversation ID for correlation.
        session_id: Session ID for per-session analysis.
        team_id: Team identifier (tenant or group based).
    """
    track_event_if_configured("LLM_User_Token_Usage", {
        "user_id": user_id,
        "agent_name": agent_name,
        "model_deployment_name": model_deployment_name,
        "input_tokens": str(usage.get("input_tokens", 0)),
        "output_tokens": str(usage.get("output_tokens", 0)),
        "total_tokens": str(usage.get("total_tokens", 0)),
        "conversation_id": conversation_id,
        "session_id": session_id,
        "team_id": team_id,
    })


def emit_team_token_event(
    team_id: str,
    agent_name: str,
    model_deployment_name: str,
    usage: dict[str, int],
    conversation_id: str = "",
    user_id: str = "",
    session_id: str = "",
) -> None:
    """Emit a per-team token usage event to Application Insights."""
    track_event_if_configured("LLM_Team_Token_Usage", {
        "team_id": team_id,
        "agent_name": agent_name,
        "model_deployment_name": model_deployment_name,
        "input_tokens": str(usage.get("input_tokens", 0)),
        "output_tokens": str(usage.get("output_tokens", 0)),
        "total_tokens": str(usage.get("total_tokens", 0)),
        "conversation_id": conversation_id,
        "user_id": user_id,
        "session_id": session_id,
    })


def emit_session_token_event(
    session_id: str,
    agent_name: str,
    model_deployment_name: str,
    usage: dict[str, int],
    conversation_id: str = "",
    user_id: str = "",
    team_id: str = "",
) -> None:
    """Emit a per-session token usage event to Application Insights."""
    track_event_if_configured("LLM_Session_Token_Usage", {
        "session_id": session_id,
        "agent_name": agent_name,
        "model_deployment_name": model_deployment_name,
        "input_tokens": str(usage.get("input_tokens", 0)),
        "output_tokens": str(usage.get("output_tokens", 0)),
        "total_tokens": str(usage.get("total_tokens", 0)),
        "conversation_id": conversation_id,
        "user_id": user_id,
        "team_id": team_id,
    })


def emit_summary_token_event(
    total_input_tokens: int,
    total_output_tokens: int,
    total_tokens: int,
    conversation_id: str = "",
    user_id: str = "",
    agent_name: str = "",
    model_deployment_name: str = "",
    session_id: str = "",
    team_id: str = "",
) -> None:
    """Emit a summary token usage event for a complete chat interaction.

    Args:
        total_input_tokens: Sum of all input tokens.
        total_output_tokens: Sum of all output tokens.
        total_tokens: Sum of all tokens.
        conversation_id: Conversation ID for correlation.
        user_id: Authenticated user's principal ID.
        agent_name: Name of the agent used.
        model_deployment_name: Model deployment name.
        session_id: Session ID for per-session analysis.
        team_id: Team identifier (tenant or group based).
    """
    track_event_if_configured("LLM_Token_Usage_Summary", {
        "total_input_tokens": str(total_input_tokens),
        "total_output_tokens": str(total_output_tokens),
        "total_tokens": str(total_tokens),
        "conversation_id": conversation_id,
        "user_id": user_id,
        "agent_name": agent_name,
        "model_deployment_name": model_deployment_name,
        "session_id": session_id,
        "team_id": team_id,
    })
    logger.info(
        "[TOKEN SUMMARY] conversation=%s user=%s agent=%s model=%s input=%d output=%d total=%d",
        conversation_id,
        user_id,
        agent_name,
        model_deployment_name,
        total_input_tokens,
        total_output_tokens,
        total_tokens,
    )


def track_all_token_events(
    agent_name: str,
    model_deployment_name: str,
    usage: dict[str, int],
    conversation_id: str = "",
    user_id: str = "",
    session_id: str = "",
    team_id: str = "",
) -> None:
    """Convenience function to emit all token tracking events at once.

    Emits per-agent, per-model, optional per-user/per-team/per-session, and summary events.

    Args:
        agent_name: Name of the agent.
        model_deployment_name: Azure OpenAI model deployment name.
        usage: Dict with input_tokens, output_tokens, total_tokens.
        conversation_id: Conversation ID for correlation.
        user_id: Authenticated user's principal ID.
        session_id: Session ID for per-session analysis.
        team_id: Team identifier (tenant or group based).
    """
    emit_agent_token_event(
        agent_name=agent_name,
        model_deployment_name=model_deployment_name,
        usage=usage,
        conversation_id=conversation_id,
        user_id=user_id,
        session_id=session_id,
        team_id=team_id,
    )
    emit_model_token_event(
        model_deployment_name=model_deployment_name,
        usage=usage,
        conversation_id=conversation_id,
        user_id=user_id,
        session_id=session_id,
        team_id=team_id,
    )
    if user_id:
        emit_user_token_event(
            user_id=user_id,
            agent_name=agent_name,
            model_deployment_name=model_deployment_name,
            usage=usage,
            conversation_id=conversation_id,
            session_id=session_id,
            team_id=team_id,
        )
    if team_id:
        emit_team_token_event(
            team_id=team_id,
            agent_name=agent_name,
            model_deployment_name=model_deployment_name,
            usage=usage,
            conversation_id=conversation_id,
            user_id=user_id,
            session_id=session_id,
        )
    if session_id:
        emit_session_token_event(
            session_id=session_id,
            agent_name=agent_name,
            model_deployment_name=model_deployment_name,
            usage=usage,
            conversation_id=conversation_id,
            user_id=user_id,
            team_id=team_id,
        )
    emit_summary_token_event(
        total_input_tokens=usage.get("input_tokens", 0),
        total_output_tokens=usage.get("output_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        conversation_id=conversation_id,
        user_id=user_id,
        agent_name=agent_name,
        model_deployment_name=model_deployment_name,
        session_id=session_id,
        team_id=team_id,
    )


def _to_int(val: object, default: int = 0) -> int:
    """Safely convert a value to int.

    Args:
        val: Value to convert.
        default: Default if conversion fails.

    Returns:
        Integer value or default.
    """
    if val is None or isinstance(val, bool):
        return default
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    if isinstance(val, str):
        s = val.strip()
        if s.isdigit():
            return int(s)
    return default
