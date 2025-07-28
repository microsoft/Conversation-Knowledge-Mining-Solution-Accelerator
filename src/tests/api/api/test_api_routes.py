import json
import pytest
from unittest.mock import AsyncMock, patch, Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import api_routes

@pytest.fixture
def create_test_client():
    def _create_client():
        app = FastAPI()
        app.include_router(api_routes.router)
        return TestClient(app)
    return _create_client


def test_fetch_chart_data_basic(create_test_client):
    with patch("api.api_routes.ChartService") as MockChartService:
        mock_instance = MockChartService.return_value
        mock_instance.fetch_chart_data = AsyncMock(return_value={"data": "mocked"})
        
        client = create_test_client()
        response = client.get("/fetchChartData")

        assert response.status_code == 200
        assert response.json() == {"data": "mocked"}



def test_fetch_filter_data_basic(create_test_client):
    with patch("api.api_routes.ChartService") as MockChartService:
        mock_instance = MockChartService.return_value
        mock_instance.fetch_filter_data = AsyncMock(return_value={"filters": "mocked"})

        client = create_test_client()
        response = client.get("/fetchFilterData")

        assert response.status_code == 200
        assert response.json() == {"filters": "mocked"}


def test_fetch_chart_data_with_filters_basic(create_test_client):
    with patch("api.api_routes.ChartService") as MockChartService:
        mock_instance = MockChartService.return_value
        mock_instance.fetch_chart_data_with_filters = AsyncMock(return_value=[
            {
                "id": "TOTAL_CALLS",
                "chart_name": "Total Calls",
                "chart_type": "card",
                "chart_value": [
                    {"name": "Total Calls", "value": float("nan"), "unit_of_measurement": ""}
                ]
            }
        ])

        client = create_test_client()
        payload = {
            "selected_filters": {
                "Topic": ["Tech"],
                "Sentiment": ["Positive"],
                "DateRange": ["Last 30 Days"]
            }
        }
        response = client.post("/fetchChartDataWithFilters", json=payload)
        expected = [
            {
                "id": "TOTAL_CALLS",
                "chart_name": "Total Calls",
                "chart_type": "card",
                "chart_value": [
                    {"name": "Total Calls", "value": None, "unit_of_measurement": ""}
                ]
            }
        ]
        assert response.status_code == 200
        assert response.json() == expected

def test_fetch_chart_data_with_filters_error(create_test_client):
    with patch("api.api_routes.ChartService") as MockChartService:
        mock_instance = MockChartService.return_value
        mock_instance.fetch_chart_data_with_filters = AsyncMock(side_effect=Exception("fail"))

        client = create_test_client()
        payload = {
            "selected_filters": {
                "Topic": ["Tech"],
                "Sentiment": ["Positive"],
                "DateRange": ["Last 30 Days"]
            }
        }
        response = client.post("/fetchChartDataWithFilters", json=payload)

        assert response.status_code == 500
        assert "error" in response.json()


def test_fetch_chart_data_error_handling(create_test_client):
    with patch("api.api_routes.ChartService") as MockChartService:
        mock_instance = MockChartService.return_value
        mock_instance.fetch_chart_data = AsyncMock(side_effect=Exception("fail"))

        client = create_test_client()
        response = client.get("/fetchChartData")

        assert response.status_code == 500
        assert "error" in response.json()


def test_chat_endpoint_basic(create_test_client):
    with patch("api.api_routes.ChatService") as MockChatService:
        mock_instance = MockChatService.return_value
        mock_instance.complete_chat_request = AsyncMock(return_value={"chart": "mocked"})
        mock_instance.stream_chat_request = AsyncMock(return_value=iter([b'{"message": "mocked stream"}']))

        client = create_test_client()
        payload = {
            "conversation_id": "test",
            "messages": [{"content": "Show me a chart"}],
            "last_rag_response": "previous data"
        }

        response = client.post("/chat", json=payload)

        assert response.status_code == 200
        assert response.json() == {"chart": "mocked"}


def test_get_layout_config_valid(create_test_client, monkeypatch):
    test_config = {"layout": "mocked"}
    monkeypatch.setenv("REACT_APP_LAYOUT_CONFIG", json.dumps(test_config))

    client = create_test_client()
    response = client.get("/layout-config")

    assert response.status_code == 200
    assert response.json() == test_config


def test_get_layout_config_invalid_json(create_test_client, monkeypatch):
    monkeypatch.setenv("REACT_APP_LAYOUT_CONFIG", "{bad json")

    client = create_test_client()
    response = client.get("/layout-config")

    assert response.status_code == 400
    assert "error" in response.json()


def test_get_chart_config_found(create_test_client, monkeypatch):
    monkeypatch.setenv("DISPLAY_CHART_DEFAULT", "true")

    client = create_test_client()
    response = client.get("/display-chart-default")

    assert response.status_code == 200
    assert response.json() == {"isChartDisplayDefault": "true"}


def test_get_chart_config_missing(create_test_client, monkeypatch):
    monkeypatch.delenv("DISPLAY_CHART_DEFAULT", raising=False)

    client = create_test_client()
    response = client.get("/display-chart-default")

    assert response.status_code == 400
    assert "error" in response.json()


def test_fetch_filter_data_error_handling(create_test_client):
    with patch("api.api_routes.ChartService") as MockChartService:
        mock_instance = MockChartService.return_value
        mock_instance.fetch_filter_data = AsyncMock(side_effect=Exception("fail"))

        client = create_test_client()
        response = client.get("/fetchFilterData")

        assert response.status_code == 500
        assert "error" in response.json()


def test_layout_config_json_decode_error(create_test_client, monkeypatch):
    monkeypatch.setenv("REACT_APP_LAYOUT_CONFIG", "not-a-json")

    client = create_test_client()
    response = client.get("/layout-config")

    assert response.status_code == 400
    assert "error" in response.json()


def test_get_chart_config_success(create_test_client, monkeypatch):
    monkeypatch.setenv("DISPLAY_CHART_DEFAULT", "false")

    client = create_test_client()
    response = client.get("/display-chart-default")

    assert response.status_code == 200
    assert response.json() == {"isChartDisplayDefault": "false"}


def test_get_chart_config_env_missing(create_test_client, monkeypatch):
    monkeypatch.delenv("DISPLAY_CHART_DEFAULT", raising=False)

    client = create_test_client()
    response = client.get("/display-chart-default")

    assert response.status_code == 400
    assert "error" in response.json()