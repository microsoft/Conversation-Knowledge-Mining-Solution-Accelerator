import json
import logging
import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from api.models.input_models import ChartFilters
from services.chat_service import ChatService
from services.chart_service import ChartService
from common.logging.event_utils import track_event_if_configured
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if the Application Insights Instrumentation Key is set in the environment variables
instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if instrumentation_key:
    # Configure Application Insights if the Instrumentation Key is found
    configure_azure_monitor(connection_string=instrumentation_key)
    logging.info("Application Insights configured with the provided Instrumentation Key")
else:
    # Log a warning if the Instrumentation Key is not found
    logging.warning("No Application Insights Instrumentation Key found. Skipping configuration")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Suppress INFO logs from 'azure.core.pipeline.policies.http_logging_policy'
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
logging.getLogger("azure.identity.aio._internal").setLevel(logging.WARNING)

# Suppress info logs from OpenTelemetry exporter
logging.getLogger("azure.monitor.opentelemetry.exporter.export._base").setLevel(
    logging.WARNING
)


@router.get("/fetchChartData")
async def fetch_chart_data():
    try:
        chart_service = ChartService()
        response = await chart_service.fetch_chart_data()
        track_event_if_configured(
            "FetchChartDataSuccess",
            {"status": "success", "source": "/fetchChartData"}
        )
        return JSONResponse(content=response)
    except Exception as e:
        logger.exception("Error in fetch_chart_data: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "Failed to fetch chart data due to an internal error."}, status_code=500)


@router.post("/fetchChartDataWithFilters")
async def fetch_chart_data_with_filters(chart_filters: ChartFilters):
    try:
        logger.info(f"Received filters: {chart_filters}")
        chart_service = ChartService()
        response = await chart_service.fetch_chart_data_with_filters(chart_filters)
        track_event_if_configured(
            "FetchChartDataWithFiltersSuccess",
            {"status": "success", "filters": chart_filters.model_dump()}
        )
        return JSONResponse(content=response)
    except Exception as e:
        logger.exception("Error in fetch_chart_data_with_filters: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "Failed to fetch chart data due to an internal error."}, status_code=500)


@router.get("/fetchFilterData")
async def fetch_filter_data():
    try:
        chart_service = ChartService()
        response = await chart_service.fetch_filter_data()
        track_event_if_configured(
            "FetchFilterDataSuccess",
            {"status": "success", "source": "/fetchFilterData"}
        )
        return JSONResponse(content=response)
    except Exception as e:
        logger.exception("Error in fetch_filter_data: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "Failed to fetch filter data due to an internal error."}, status_code=500)


@router.post("/chat")
async def conversation(request: Request):
    try:
        # Get the request JSON and last RAG response from the client
        request_json = await request.json()
        last_rag_response = request_json.get("last_rag_response")
        conversation_id = request_json.get("conversation_id")
        logger.info(f"Received last_rag_response: {last_rag_response}")

        query = request_json.get("messages")[-1].get("content")
        is_chart_query = any(
            term in query.lower()
            for term in ["chart", "graph", "visualize", "plot"]
        )
        chat_service = ChatService(request=request)
        if not is_chart_query:
            result = await chat_service.stream_chat_request(request_json, conversation_id, query)
            track_event_if_configured(
                "ChatStreamSuccess",
                {"conversation_id": conversation_id, "query": query}
            )
            return StreamingResponse(result, media_type="application/json-lines")
        else:
            result = await chat_service.complete_chat_request(query, last_rag_response)
            track_event_if_configured(
                "ChartChatSuccess",
                {"conversation_id": conversation_id, "query": query}
            )
            return JSONResponse(content=result)

    except Exception as ex:
        logger.exception("Error in conversation endpoint: %s", str(ex))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(ex)
            span.set_status(Status(StatusCode.ERROR, str(ex)))
        return JSONResponse(content={"error": "An internal error occurred while processing the conversation."}, status_code=500)


@router.get("/layout-config")
async def get_layout_config():
    layout_config_str = os.getenv("REACT_APP_LAYOUT_CONFIG", "")
    if layout_config_str:
        try:
            layout_config_json = json.loads(layout_config_str)
            track_event_if_configured("LayoutConfigFetched", {"status": "success"})  # Parse the string into JSON
            return JSONResponse(content=layout_config_json)    # Return the parsed JSON
        except json.JSONDecodeError as e:
            logger.exception("Failed to parse layout config JSON: %s", str(e))
            span = trace.get_current_span()
            if span is not None:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
            return JSONResponse(content={"error": "Invalid layout configuration format."}, status_code=400)
    track_event_if_configured("LayoutConfigNotFound", {})
    return JSONResponse(content={"error": "Layout config not found in environment variables"}, status_code=400)


@router.get("/display-chart-default")
async def get_chart_config():
    chart_config = os.getenv("DISPLAY_CHART_DEFAULT", "")
    if chart_config:
        track_event_if_configured("ChartDisplayDefaultFetched", {"value": chart_config})
        return JSONResponse(content={"isChartDisplayDefault": chart_config})
    track_event_if_configured("ChartDisplayDefaultNotFound", {})
    return JSONResponse(content={"error": "DISPLAY_CHART_DEFAULT flag not found in environment variables"}, status_code=400)
