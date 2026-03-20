"""Utility functions for tracking events with Azure Monitor Application Insights.

This module provides helper functions to log custom events to Azure Application Insights,
if the instrumentation key is configured in the environment.
"""

import logging
import os
from azure.monitor.events.extension import track_event

logger = logging.getLogger(__name__)


def track_event_if_configured(event_name: str, event_data: dict):
    """Track custom event to Application Insights if configured.

    Telemetry is strictly best-effort: any failure is logged at WARNING
    level and never propagated, so callers are not affected.

    Args:
        event_name: Name of the event to track
        event_data: Dictionary of event properties
    """
    instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if instrumentation_key:
        try:
            track_event(event_name, event_data)
        except Exception:
            logger.warning("Failed to track event '%s'; telemetry is best-effort", event_name, exc_info=True)
    else:
        logger.warning("Skipping track_event for %s: Application Insights is not configured", event_name)
