import logging
from fastapi import HTTPException, status

from api.models.input_models import ChartFilters
from common.database.sqldb_service import adjust_processed_data_dates, fetch_chart_data, fetch_filters_data

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChartService:
    """
    Service class for handling chart-related data retrieval.
    """

    async def fetch_filter_data(self):
        """
        Fetch filter data for charts.
        """
        try:
            await adjust_processed_data_dates()
            return await fetch_filters_data()
        except Exception as e:
            logger.error("Error in fetch_filter_data: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while fetching filter data."
            )

    async def fetch_chart_data(self):
        """
        Fetch chart data.
        """
        try:
            return await fetch_chart_data()
        except Exception as e:
            logger.error("Error in fetch_chart_data: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while fetching chart data."
            )

    async def fetch_chart_data_with_filters(self, chart_filters: ChartFilters):
        """
        Fetch chart data based on applied filters.
        """
        try:
            return await fetch_chart_data(chart_filters)
        except Exception as e:
            logger.error("Error in fetch_chart_data_with_filters: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while fetching filtered chart data."
            )
