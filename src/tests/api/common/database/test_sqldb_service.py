import pytest
import pyodbc
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from common.database import sqldb_service


@pytest.fixture
def mock_db_conn():
    """Fixture to mock pyodbc.connect and its cursor."""
    with patch("pyodbc.connect") as mock_connect:
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        yield mock_conn, mock_cursor


@pytest.fixture
def token_fixture():
    """Fixture to mock get_azure_credential_async with async context support."""
    with patch("common.database.sqldb_service.get_azure_credential_async", new_callable=AsyncMock) as mock_cred:
        mock_cred_instance = AsyncMock()

        async def mock_get_token(*args, **kwargs):
            token_mock = MagicMock()
            token_mock.token = "dummy_token"
            return token_mock

        mock_cred_instance.get_token.side_effect = mock_get_token

        async def aenter(*args, **kwargs):
            return mock_cred_instance

        async def aexit(*args, **kwargs):
            pass

        mock_cred_instance.__aenter__.side_effect = aenter
        mock_cred_instance.__aexit__.side_effect = aexit
        mock_cred.return_value = mock_cred_instance

        yield mock_cred_instance


class TestSqlDbService:

    @pytest.mark.asyncio
    async def test_get_db_connection_success(self, mock_db_conn, token_fixture):
        conn = await sqldb_service.get_db_connection()
        assert conn is not None

    @pytest.mark.asyncio
    async def test_get_db_connection_fallback_to_sql_auth(self):
        """Test fallback to SQL auth when token auth fails."""
        with patch("pyodbc.connect") as mock_connect, \
             patch("common.database.sqldb_service.get_azure_credential_async", new_callable=AsyncMock) as mock_cred:

            mock_token_instance = AsyncMock()

            async def get_token_mock(*args, **kwargs):
                token_mock = MagicMock()
                token_mock.token = "dummy_token"
                return token_mock

            mock_token_instance.get_token.side_effect = get_token_mock

            async def aenter(*args, **kwargs):
                raise pyodbc.Error("Simulated failure")

            mock_token_instance.__aenter__.side_effect = aenter
            mock_token_instance.__aexit__.side_effect = AsyncMock()
            mock_cred.return_value = mock_token_instance

            fallback_conn = MagicMock()
            mock_connect.return_value = fallback_conn

            conn = await sqldb_service.get_db_connection()
            assert conn is fallback_conn

    @pytest.mark.asyncio
    async def test_adjust_processed_data_dates(self, mock_db_conn, token_fixture):
        mock_conn, mock_cursor = mock_db_conn
        old_date = datetime.today().replace(year=datetime.today().year - 1)
        mock_cursor.fetchone.return_value = [old_date]

        await sqldb_service.adjust_processed_data_dates()
        assert mock_cursor.execute.call_count >= 4
        assert mock_conn.commit.called

    @pytest.mark.asyncio
    async def test_fetch_filters_data(self, mock_db_conn, token_fixture):
        _, mock_cursor = mock_db_conn
        mock_cursor.fetchall.return_value = [
            ("Topic", "Billing", "Billing"),
            ("Sentiment", "positive", "positive"),
            ("Satisfaction", "yes", "yes"),
            ("DateRange", "Last 7 days", "Last 7 days"),
        ]
        mock_cursor.description = [("filter_name",), ("displayValue",), ("key1",)]

        result = await sqldb_service.fetch_filters_data()
        assert isinstance(result, list)
        assert {item["filter_name"] for item in result} == {"Topic", "Sentiment", "Satisfaction", "DateRange"}

    @pytest.mark.asyncio
    async def test_fetch_chart_data_with_filters(self, mock_db_conn, token_fixture):
        _, mock_cursor = mock_db_conn
        mock_cursor.fetchall.side_effect = [
            [("TOTAL_CALLS", "Total Calls", "card", "Total Calls", 100, "")],
            [("Topic A", "TOPICS", "Trending Topics", "table", "positive", 42)],
            [("keyphrase", "KEY_PHRASES", "Key Phrases", "wordcloud", 20, "positive")]
        ]
        descriptions = [
            [("id",), ("chart_name",), ("chart_type",), ("name",), ("value",), ("unit_of_measurement",)],
            [("name",), ("id",), ("chart_name",), ("chart_type",), ("average_sentiment",), ("call_frequency",)],
            [("text",), ("id",), ("chart_name",), ("chart_type",), ("size",), ("average_sentiment",)],
        ]

        def exec_side_effect(*args, **kwargs):
            call = mock_cursor.execute.call_count - 1
            mock_cursor.description = descriptions[call]

        mock_cursor.execute.side_effect = exec_side_effect

        filters = MagicMock()
        filters.model_dump.return_value = {
            "selected_filters": {
                "Topic": ["Topic A"],
                "Sentiment": ["positive"],
                "Satisfaction": ["yes"],
                "DateRange": ["Last 7 days"]
            }
        }

        result = await sqldb_service.fetch_chart_data(chart_filters=filters)
        assert isinstance(result, list)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_fetch_chart_data_with_invalid_model(self, mock_db_conn, token_fixture):
        _, mock_cursor = mock_db_conn
        mock_cursor.fetchall.side_effect = [
            [("TOTAL_CALLS", "Total Calls", "card", "Total Calls", 100, "")],
            [("Topic A", "TOPICS", "Trending Topics", "table", "positive", 42)],
            [("keyphrase", "KEY_PHRASES", "Key Phrases", "wordcloud", 20, "positive")]
        ]
        descriptions = [
            [("id",), ("chart_name",), ("chart_type",), ("name",), ("value",), ("unit_of_measurement",)],
            [("name",), ("id",), ("chart_name",), ("chart_type",), ("average_sentiment",), ("call_frequency",)],
            [("text",), ("id",), ("chart_name",), ("chart_type",), ("size",), ("average_sentiment",)],
        ]

        def exec_side_effect(*args, **kwargs):
            call = mock_cursor.execute.call_count - 1
            mock_cursor.description = descriptions[call]

        mock_cursor.execute.side_effect = exec_side_effect

        filters = MagicMock()
        filters.model_dump.side_effect = Exception("Invalid model")

        result = await sqldb_service.fetch_chart_data(chart_filters=filters)
        assert isinstance(result, list)
        assert len(result) == 3

    @pytest.mark.asyncio
    @pytest.mark.parametrize("date_range_value", [
        "Last 14 days", "Last 90 days", "Year to Date"
    ])
    async def test_fetch_chart_data_with_various_date_ranges(self, mock_db_conn, token_fixture, date_range_value):
        _, mock_cursor = mock_db_conn
        mock_cursor.fetchall.side_effect = [
            [("TOTAL_CALLS", "Total Calls", "card", "Total Calls", 100, "")],
            [("Topic A", "TOPICS", "Trending Topics", "table", "positive", 42)],
            [(f"keyphrase", "KEY_PHRASES", "Key Phrases", "wordcloud", 10, "positive")]
        ]
        descriptions = [
            [("id",), ("chart_name",), ("chart_type",), ("name",), ("value",), ("unit_of_measurement",)],
            [("name",), ("id",), ("chart_name",), ("chart_type",), ("average_sentiment",), ("call_frequency",)],
            [("text",), ("id",), ("chart_name",), ("chart_type",), ("size",), ("average_sentiment",)],
        ]

        def exec_side_effect(*args, **kwargs):
            call = mock_cursor.execute.call_count - 1
            mock_cursor.description = descriptions[call]

        mock_cursor.execute.side_effect = exec_side_effect

        filters = MagicMock()
        filters.model_dump.return_value = {"selected_filters": {"DateRange": [date_range_value]}}

        result = await sqldb_service.fetch_chart_data(chart_filters=filters)
        assert isinstance(result, list)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_execute_sql_query(self, mock_db_conn, token_fixture):
        _, mock_cursor = mock_db_conn
        mock_cursor.fetchall.return_value = [(1,), (2,), (3,)]

        result = await sqldb_service.execute_sql_query("SELECT 1")
        assert result == "(1,)(2,)(3,)"

    @pytest.mark.asyncio
    async def test_execute_sql_query_exception(self, mock_db_conn, token_fixture):
        _, mock_cursor = mock_db_conn
        mock_cursor.execute.side_effect = Exception("Invalid SQL")

        result = await sqldb_service.execute_sql_query("INVALID SQL")
        assert result is None
