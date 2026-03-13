"""Utility functions for tracking events with Azure Monitor Application Insights.

This module provides helper functions to log custom events to Azure Application Insights,
if the instrumentation key is configured in the environment.
"""

import logging
import os
from azure.monitor.events.extension import track_event


def track_event_if_configured(event_name: str, event_data: dict):
    """Track custom event to Application Insights if configured.

    Args:
        event_name: Name of the event to track
        event_data: Dictionary of event properties
    """
    instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if instrumentation_key:
        track_event(event_name, event_data)
    else:
        logging.warning("Skipping track_event for %s as Application Insights is not configured", event_name)
