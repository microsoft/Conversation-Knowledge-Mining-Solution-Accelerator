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
    return dashboard_service.get_dashboard(filters or None, refresh)
