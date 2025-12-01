"""Utility functions for tracking events with Azure Monitor Application Insights.

This module provides helper functions to log custom events to Azure Application Insights,
if the instrumentation key is configured in the environment.
"""

import logging
import os
from azure.monitor.events.extension import track_event


def track_event_if_configured(event_name: str, event_data: dict):
    instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    print(f"Instrumentation Key: {instrumentation_key}")
    if instrumentation_key:
        track_event(event_name, event_data)
    else:
        logging.warning(f"Skipping track_event for {event_name} as Application Insights is not configured")
