# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Token usage tracking for LLM calls in the Conversation Knowledge Mining Solution Accelerator.

Extracts token counts from Azure OpenAI agent framework responses and emits
custom events to Application Insights for monitoring, cost estimation, and
performance optimization.

Tracks usage across four dimensions:
- Per Agent: Which agent/orchestrator consumed tokens
- Per User: Which user session triggered the consumption
- Per Model: Which model deployment was used
- Per Team: Which team the user belongs to (derived from configuration)
"""

import logging
import os
from typing import Any

from common.logging.event_utils import track_event_if_configured

logger = logging.getLogger(__name__)


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


def extract_token_usage(response: Any) -> dict[str, int]:
    """Extract token usage from an agent framework response.

    Checks multiple attribute paths to handle different response shapes
    from the agent framework SDK (streaming final chunks, run results, etc.).

    Args:
        response: The response object from agent.run() or a streaming chunk.

    Returns:
        Dict with keys: input_tokens, output_tokens, total_tokens.
        All default to 0 if not found.
    """
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0

    # Path 1: usage_details attribute (set by agent framework SDK)
    usage_details = getattr(response, "usage_details", None)
    if usage_details is not None:
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
        else:
            # UsageDetails object with attributes
            input_tokens = _to_int(
                getattr(usage_details, "input_token_count", 0)
                or getattr(usage_details, "prompt_tokens", 0)
            )
            output_tokens = _to_int(
                getattr(usage_details, "output_token_count", 0)
                or getattr(usage_details, "completion_tokens", 0)
            )
            total_tokens = _to_int(
                getattr(usage_details, "total_token_count", 0)
            ) or (input_tokens + output_tokens)

    # Path 2: usage attribute directly on response
    if total_tokens == 0:
        usage_obj = getattr(response, "usage", None)
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

    # Path 3: raw_representation.usage (raw Azure OpenAI response)
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


def extract_token_usage_from_stream_chunk(chunk: Any) -> dict[str, int]:
    """Extract token usage from a streaming chunk if available.

    During streaming, token usage is typically reported in the final chunk
    or via a special usage field on delta events.

    Args:
        chunk: A streaming chunk from agent.run(stream=True).

    Returns:
        Dict with keys: input_tokens, output_tokens, total_tokens.
        All default to 0 if usage not present in this chunk.
    """
    # Check if chunk has usage info (typically the last chunk in a stream)
    usage = extract_token_usage(chunk)
    if usage["total_tokens"] > 0:
        return usage

    # Check for usage in chunk metadata
    metadata = getattr(chunk, "metadata", None)
    if metadata is not None:
        usage_data = metadata.get("usage", None) if isinstance(metadata, dict) else getattr(metadata, "usage", None)
        if usage_data:
            return extract_token_usage_from_dict(usage_data)

    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def extract_token_usage_from_dict(usage_data: Any) -> dict[str, int]:
    """Extract token usage from a dictionary or object.

    Args:
        usage_data: A dict or object containing token count fields.

    Returns:
        Dict with keys: input_tokens, output_tokens, total_tokens.
    """
    if isinstance(usage_data, dict):
        input_tokens = _to_int(
            usage_data.get("prompt_tokens")
            or usage_data.get("input_tokens")
            or usage_data.get("input_token_count")
        )
        output_tokens = _to_int(
            usage_data.get("completion_tokens")
            or usage_data.get("output_tokens")
            or usage_data.get("output_token_count")
        )
        total_tokens = _to_int(
            usage_data.get("total_tokens")
            or usage_data.get("total_token_count")
        ) or (input_tokens + output_tokens)
    else:
        input_tokens = _to_int(
            getattr(usage_data, "prompt_tokens", 0)
            or getattr(usage_data, "input_tokens", 0)
        )
        output_tokens = _to_int(
            getattr(usage_data, "completion_tokens", 0)
            or getattr(usage_data, "output_tokens", 0)
        )
        total_tokens = _to_int(
            getattr(usage_data, "total_tokens", 0)
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
) -> None:
    """Emit a per-agent token usage event to Application Insights.

    Args:
        agent_name: Name of the agent (e.g. 'orchestrator', 'title_agent').
        model_deployment_name: Azure OpenAI model deployment name.
        usage: Dict with input_tokens, output_tokens, total_tokens.
        conversation_id: Conversation ID for correlation.
        user_id: User ID who triggered the agent call.
    """
    track_event_if_configured("LLM_Agent_Token_Usage", {
        "agent_name": agent_name,
        "input_tokens": str(usage.get("input_tokens", 0)),
        "output_tokens": str(usage.get("output_tokens", 0)),
        "total_tokens": str(usage.get("total_tokens", 0)),
        "model_deployment_name": model_deployment_name,
        "conversation_id": conversation_id,
        "user_id": user_id,
    })
    logger.info(
        "[TOKEN USAGE] agent=%s model=%s input=%d output=%d total=%d conversation=%s user=%s",
        agent_name,
        model_deployment_name,
        usage.get("input_tokens", 0),
        usage.get("output_tokens", 0),
        usage.get("total_tokens", 0),
        conversation_id,
        user_id,
    )


def emit_user_token_event(
    user_id: str,
    usage: dict[str, int],
    agent_name: str = "",
    model_deployment_name: str = "",
    conversation_id: str = "",
) -> None:
    """Emit a per-user token usage event to Application Insights.

    Args:
        user_id: User principal ID or identifier.
        usage: Dict with input_tokens, output_tokens, total_tokens.
        agent_name: Name of the agent that consumed tokens.
        model_deployment_name: Azure OpenAI model deployment name.
        conversation_id: Conversation ID for correlation.
    """
    track_event_if_configured("LLM_User_Token_Usage", {
        "user_id": user_id,
        "input_tokens": str(usage.get("input_tokens", 0)),
        "output_tokens": str(usage.get("output_tokens", 0)),
        "total_tokens": str(usage.get("total_tokens", 0)),
        "agent_name": agent_name,
        "model_deployment_name": model_deployment_name,
        "conversation_id": conversation_id,
    })


def emit_team_token_event(
    team_name: str,
    usage: dict[str, int],
    user_id: str = "",
    agent_name: str = "",
    model_deployment_name: str = "",
    conversation_id: str = "",
) -> None:
    """Emit a per-team token usage event to Application Insights.

    Args:
        team_name: Team name or identifier.
        usage: Dict with input_tokens, output_tokens, total_tokens.
        user_id: User ID within the team.
        agent_name: Name of the agent that consumed tokens.
        model_deployment_name: Azure OpenAI model deployment name.
        conversation_id: Conversation ID for correlation.
    """
    track_event_if_configured("LLM_Team_Token_Usage", {
        "team_name": team_name,
        "input_tokens": str(usage.get("input_tokens", 0)),
        "output_tokens": str(usage.get("output_tokens", 0)),
        "total_tokens": str(usage.get("total_tokens", 0)),
        "user_id": user_id,
        "agent_name": agent_name,
        "model_deployment_name": model_deployment_name,
        "conversation_id": conversation_id,
    })


def emit_model_token_event(
    model_deployment_name: str,
    usage: dict[str, int],
    conversation_id: str = "",
    user_id: str = "",
    agent_name: str = "",
) -> None:
    """Emit a per-model token usage event to Application Insights.

    Args:
        model_deployment_name: Azure OpenAI model deployment name.
        usage: Dict with input_tokens, output_tokens, total_tokens.
        conversation_id: Conversation ID for correlation.
        user_id: User ID who triggered the model call.
        agent_name: Name of the agent that used this model.
    """
    track_event_if_configured("LLM_Model_Token_Usage", {
        "model_deployment_name": model_deployment_name,
        "input_tokens": str(usage.get("input_tokens", 0)),
        "output_tokens": str(usage.get("output_tokens", 0)),
        "total_tokens": str(usage.get("total_tokens", 0)),
        "conversation_id": conversation_id,
        "user_id": user_id,
        "agent_name": agent_name,
    })


def emit_summary_token_event(
    total_input_tokens: int,
    total_output_tokens: int,
    total_tokens: int,
    conversation_id: str = "",
    user_id: str = "",
    team_name: str = "",
    agent_name: str = "",
    model_deployment_name: str = "",
) -> None:
    """Emit a summary token usage event for a complete chat interaction.

    Args:
        total_input_tokens: Sum of all input tokens across the interaction.
        total_output_tokens: Sum of all output tokens across the interaction.
        total_tokens: Sum of all tokens across the interaction.
        conversation_id: Conversation ID.
        user_id: User ID.
        team_name: Team name.
        agent_name: Agent that handled the interaction.
        model_deployment_name: Model deployment used.
    """
    track_event_if_configured("LLM_Token_Usage_Summary", {
        "total_input_tokens": str(total_input_tokens),
        "total_output_tokens": str(total_output_tokens),
        "total_tokens": str(total_tokens),
        "conversation_id": conversation_id,
        "user_id": user_id,
        "team_name": team_name,
        "agent_name": agent_name,
        "model_deployment_name": model_deployment_name,
    })
    logger.info(
        "[TOKEN SUMMARY] conversation=%s user=%s team=%s agent=%s model=%s input=%d output=%d total=%d",
        conversation_id,
        user_id,
        team_name,
        agent_name,
        model_deployment_name,
        total_input_tokens,
        total_output_tokens,
        total_tokens,
    )


def emit_all_token_events(
    agent_name: str,
    model_deployment_name: str,
    usage: dict[str, int],
    conversation_id: str = "",
    user_id: str = "",
    team_name: str = "",
) -> None:
    """Emit all token usage events (agent, user, team, model, summary) in one call.

    This is a convenience function that emits events across all tracking dimensions.
    Use this after each LLM interaction completes to ensure comprehensive tracking.

    Args:
        agent_name: Name of the agent.
        model_deployment_name: Azure OpenAI model deployment name.
        usage: Dict with input_tokens, output_tokens, total_tokens.
        conversation_id: Conversation ID for correlation.
        user_id: User ID who triggered the interaction.
        team_name: Team name (defaults to env var TEAM_NAME if not provided).
    """
    if not team_name:
        team_name = os.getenv("TEAM_NAME", "default")

    # Only emit if there are actual tokens to report
    if usage.get("total_tokens", 0) == 0:
        logger.debug(
            "Skipping token event emission: no tokens reported for agent=%s conversation=%s",
            agent_name,
            conversation_id,
        )
        return

    # Per-agent tracking
    emit_agent_token_event(
        agent_name=agent_name,
        model_deployment_name=model_deployment_name,
        usage=usage,
        conversation_id=conversation_id,
        user_id=user_id,
    )

    # Per-user tracking
    if user_id:
        emit_user_token_event(
            user_id=user_id,
            usage=usage,
            agent_name=agent_name,
            model_deployment_name=model_deployment_name,
            conversation_id=conversation_id,
        )

    # Per-team tracking
    emit_team_token_event(
        team_name=team_name,
        usage=usage,
        user_id=user_id,
        agent_name=agent_name,
        model_deployment_name=model_deployment_name,
        conversation_id=conversation_id,
    )

    # Per-model tracking
    emit_model_token_event(
        model_deployment_name=model_deployment_name,
        usage=usage,
        conversation_id=conversation_id,
        user_id=user_id,
        agent_name=agent_name,
    )

    # Summary event
    emit_summary_token_event(
        total_input_tokens=usage.get("input_tokens", 0),
        total_output_tokens=usage.get("output_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        conversation_id=conversation_id,
        user_id=user_id,
        team_name=team_name,
        agent_name=agent_name,
        model_deployment_name=model_deployment_name,
    )
