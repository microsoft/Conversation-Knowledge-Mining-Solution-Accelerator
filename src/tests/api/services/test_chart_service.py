import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


@patch("common.database.sqldb_service.adjust_processed_data_dates", new_callable=MagicMock)
@patch("common.database.sqldb_service.fetch_filters_data", new_callable=MagicMock)
@patch("common.database.sqldb_service.fetch_chart_data", new_callable=AsyncMock)
@patch("api.models.input_models.ChartFilters", new_callable=MagicMock)
@pytest.fixture
def patched_imports(_, __, ___, ____):
    """
    Apply patches to dependencies before importing ChartService.
    Returns patched ChartService
    """
    # Import the service under test only after patching dependencies
    with patch("services.chart_service.adjust_processed_data_dates"), \
         patch("services.chart_service.fetch_filters_data"), \
         patch("services.chart_service.fetch_chart_data"):
        from services.chart_service import ChartService
        return ChartService

# ---- Import service under test ----
with patch("common.database.sqldb_service.adjust_processed_data_dates", MagicMock()), \
     patch("common.database.sqldb_service.fetch_filters_data", MagicMock()), \
     patch("common.database.sqldb_service.fetch_chart_data", AsyncMock()), \
     patch("api.models.input_models.ChartFilters", MagicMock()):
    from services.chart_service import ChartService

@pytest.fixture
def chart_service():
    """
    Returns a clean instance of the ChartService for each test.
    """
    return ChartService()


@patch("services.chart_service.adjust_processed_data_dates", new_callable=AsyncMock)
@patch("services.chart_service.fetch_filters_data", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_fetch_filter_data_success(mock_fetch_filters_data, mock_adjust_dates, chart_service):
    mock_adjust_dates.return_value = None
    mock_fetch_filters_data.return_value = {"data": "filter_data"}

    result = await chart_service.fetch_filter_data()
    assert result == {"data": "filter_data"}



@patch("services.chart_service.adjust_processed_data_dates", new_callable=AsyncMock, side_effect=Exception("Failed"))
@patch("services.chart_service.fetch_filters_data", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_fetch_filter_data_failure(mock_fetch_filters_data, mock_adjust_dates, chart_service):
    with pytest.raises(HTTPException) as exc_info:
        await chart_service.fetch_filter_data()
    assert exc_info.value.status_code == 500


@patch("services.chart_service.fetch_chart_data", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_fetch_chart_data_success(mock_fetch_chart_data, chart_service):
    mock_fetch_chart_data.return_value = {"data": "chart_data"}
    result = await chart_service.fetch_chart_data()
    assert result == {"data": "chart_data"}


@patch("services.chart_service.fetch_chart_data", new_callable=AsyncMock, side_effect=Exception("DB error"))
@pytest.mark.asyncio
async def test_fetch_chart_data_failure(mock_fetch_chart_data, chart_service):
    with pytest.raises(HTTPException) as exc_info:
        await chart_service.fetch_chart_data()
    assert exc_info.value.status_code == 500


@patch("services.chart_service.fetch_chart_data", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_fetch_chart_data_with_filters_success(mock_fetch_chart_data, chart_service):
    mock_fetch_chart_data.return_value = {"data": "filtered_chart_data"}
    fake_filters = MagicMock()

    result = await chart_service.fetch_chart_data_with_filters(fake_filters)
    assert result == {"data": "filtered_chart_data"}


@patch("services.chart_service.fetch_chart_data", new_callable=AsyncMock, side_effect=Exception("Failure"))
@pytest.mark.asyncio
async def test_fetch_chart_data_with_filters_failure(mock_fetch_chart_data, chart_service):
    fake_filters = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await chart_service.fetch_chart_data_with_filters(fake_filters)
    assert exc_info.value.status_code == 500
