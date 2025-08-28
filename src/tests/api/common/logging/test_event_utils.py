import logging
from unittest.mock import patch, MagicMock
import pytest

from common.logging.event_utils import track_event_if_configured  

@pytest.fixture
def event_data():
    return {"user": "test_user", "action": "test_action"}


def test_track_event_with_instrumentation_key(monkeypatch, event_data):
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "some-key")

    with patch("common.logging.event_utils.track_event") as mock_track_event:
        track_event_if_configured("TestEvent", event_data)
        mock_track_event.assert_called_once_with("TestEvent", event_data)


def test_track_event_without_instrumentation_key(monkeypatch, event_data, caplog):
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

    with patch("common.logging.event_utils.track_event") as mock_track_event:
        with caplog.at_level(logging.WARNING):
            track_event_if_configured("TestEvent", event_data)
            mock_track_event.assert_not_called()
            assert "Skipping track_event for TestEvent as Application Insights is not configured" in caplog.text
