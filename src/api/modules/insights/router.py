"""Insights dashboard API router."""

from fastapi import APIRouter, Request, Query

from src.api.modules.insights.service import dashboard_service

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    request: Request,
    refresh: bool = Query(False, description="Force re-plan insights via LLM"),
):
    """Return LLM-planned, SQL-computed insight visualizations.

    Pipeline:
      1. Extract schema + stats from SQL
      2. LLM plans which insights matter (cached until schema changes or refresh=true)
      3. SQL computes exact numbers for each planned insight
      4. Returns chart-ready JSON

    Accepts filter query params:
      ?sentiment=Positive&mined_topic=Billing+Issues&refresh=true
    """
    reserved = {"refresh"}
    filters = {k: v for k, v in request.query_params.items() if k not in reserved}
    result = dashboard_service.get_dashboard(filters or None, refresh)
    
    # If no documents but result is empty, check for external data sources
    # and provide a helpful message
    if result.get("headline") == "No Data Available":
        try:
            from src.api.modules.data_sources.registry import registry
            sources = registry.list_sources()
            if sources and len(sources) > 0:
                result["headline"] = "External Data Source Detected"
                result["summary"] = "Insights are available from your external data sources. Connect or configure a data source to view detailed analytics."
                result["runtime"]["summarySignals"] = [result["headline"], result["summary"]]
        except Exception:
            pass  # Continue with default empty state if registry check fails
    
    return result

