from __future__ import annotations

from typing import Optional

from src.api.modules.runtime.registry import runtime_registry


class AnalyticsEngine:
    """Capability-driven dashboard generation over all available runtime sources."""

    def _resolve_external_source(self, filters: Optional[dict]) -> tuple[Optional[str], Optional[str]]:
        if not filters:
            return None, None
        source_name = str(filters.get("source") or "").strip()
        if not source_name:
            return None, None
        resolved_id, resolved_name = runtime_registry.resolve_external_source(source_name)
        return resolved_id, resolved_name

    def _build_runtime_only_dashboard(self, sql_dashboard_service, source_id: str, source_name: str, filters: Optional[dict]) -> dict:
        from src.api.modules.data_sources.registry import data_source_registry

        effective_filters = dict(filters or {})
        effective_filters.pop("source", None)

        source_agg = runtime_registry.aggregate({"source": source_id, "field": "source", "top": 12, "filters": effective_filters})
        cfg = data_source_registry.get(source_id)
        has_type_field = bool(getattr(getattr(cfg, "field_mapping", None), "type_field", ""))
        type_agg = runtime_registry.aggregate({"source": source_id, "field": "type", "top": 12, "filters": effective_filters}) if has_type_field else {"items": []}
        extraction = runtime_registry.extraction_facets(source=source_id, filters=effective_filters, count=160, top=20)
        topic_items = extraction.get("topics", [])
        entity_items = extraction.get("entities", [])
        phrase_items = extraction.get("key_phrases", [])
        theme_items = phrase_items[:12] if phrase_items else topic_items[:12]
        top_theme_labels = [str(i.get("label") or "") for i in theme_items[:3] if str(i.get("label") or "").strip()]
        top_entity_labels = [str(i.get("label") or "") for i in entity_items[:3] if str(i.get("label") or "").strip()]
        total_records = runtime_registry.count(source=source_id, filters=effective_filters)

        sections = [
            {
                "id": "source-distribution",
                "title": "Knowledge Source Coverage",
                "type": "distribution",
                "charts": [
                    {
                        "insight_type": "distribution",
                        "title": "Records by source",
                        "description": "Coverage for the selected connected knowledge source.",
                        "visualization": "donut",
                        "field": "source",
                        "data": source_agg.get("items", []),
                    },
                    {
                        "insight_type": "distribution",
                        "title": "Records by type",
                        "description": "Distribution of content types for the selected source.",
                        "visualization": "bar",
                        "field": "type",
                        "data": type_agg.get("items", []),
                    },
                ],
            }
        ]

        if theme_items or entity_items:
            extraction_charts = []
            if theme_items:
                extraction_charts.append(
                    {
                        "insight_type": "distribution",
                        "title": "Top themes",
                        "description": "Most frequent policy/issues themes detected in this source.",
                        "visualization": "horizontal_bar",
                        "field": "topics",
                        "data": theme_items,
                    }
                )
            if entity_items:
                extraction_charts.append(
                    {
                        "insight_type": "distribution",
                        "title": "Top entities",
                        "description": "Most frequent entities detected in this source.",
                        "visualization": "horizontal_bar",
                        "field": "entities",
                        "data": entity_items[:12],
                    }
                )

            sections.append(
                {
                    "id": "extraction-signals",
                    "title": "Extraction Signals",
                    "type": "text_analysis",
                    "charts": extraction_charts,
                }
            )

        response = {
            "data_context": {
                "total_records": total_records,
                "filtered_records": total_records,
                "filters_applied": {**(filters or {}), "source": source_name},
            },
            "headline": f"{source_name} Insights",
            "summary": f"Analyzed {total_records} records from the {source_name} connection.",
            "key_insights": (
                [
                    f"Top themes detected: {', '.join(top_theme_labels)}." if top_theme_labels else "Theme extraction found limited high-signal terms.",
                    f"Most referenced entities: {', '.join(top_entity_labels)}." if top_entity_labels else "Entity extraction found limited high-signal entities.",
                    "Use Explore to validate these findings against source passages and narrow by filters.",
                ]
            ),
            "standout_findings": [],
            "kpis": [
                {"metric": "records", "label": "Records analyzed", "value": total_records, "format": "number"},
                {"metric": "source_count", "label": "Active sources", "value": 1, "format": "number"},
                {"metric": "topics_count", "label": "Topics identified", "value": len(theme_items), "format": "number"},
                {"metric": "entities_count", "label": "Entities extracted", "value": len(entity_items), "format": "number"},
            ],
            "sections": sections,
            "filters": [
                {
                    "field": "source",
                    "label": "Source",
                    "type": "categorical",
                    "multi_select": False,
                    "values": [source_name],
                },
            ],
            "suggested_questions": [
                f"What are the top 3 employee-impact themes in {source_name}?",
                f"Which benefits, exclusions, or requirements appear most often in {source_name}?",
                f"What operational risks should support teams prioritize from {source_name}?",
            ],
        }
        if has_type_field:
            response["filters"].append(
                {
                    "field": "type",
                    "label": "Type",
                    "type": "categorical",
                    "multi_select": False,
                    "values": [str(item.get("label") or "unknown") for item in type_agg.get("items", [])[:30]],
                }
            )
        response["runtime"] = sql_dashboard_service._to_runtime_payload(response)
        return response

    def _build_source_sections(self, filters: Optional[dict]) -> tuple[list[dict], list[dict], int, int]:
        source_agg = runtime_registry.aggregate({"source": "all", "field": "source", "top": 12, "filters": filters})
        type_agg = runtime_registry.aggregate({"source": "all", "field": "type", "top": 12, "filters": filters})

        source_items = source_agg.get("items", []) if isinstance(source_agg, dict) else []
        type_items = type_agg.get("items", []) if isinstance(type_agg, dict) else []
        if not source_items and not type_items:
            return [], [], 0, 0

        sampled_records = int(source_agg.get("total") or 0)
        source_count = len(source_items)

        sections = [
            {
                "id": "source-distribution",
                "title": "Knowledge Source Coverage",
                "type": "distribution",
                "charts": [
                    {
                        "insight_type": "distribution",
                        "title": "Records by source",
                        "description": "Coverage across uploaded, seeded, and connected sources.",
                        "visualization": "donut",
                        "field": "source",
                        "data": source_items,
                    },
                    {
                        "insight_type": "distribution",
                        "title": "Records by type",
                        "description": "Distribution of content types in the active scope.",
                        "visualization": "bar",
                        "field": "type",
                        "data": type_items,
                    },
                ],
            }
        ]

        filters_out = [
            {
                "field": "source",
                "label": "Source",
                "type": "categorical",
                "multi_select": False,
                "values": [str(item.get("label") or "unknown") for item in source_items[:30]],
            },
            {
                "field": "type",
                "label": "Type",
                "type": "categorical",
                "multi_select": False,
                "values": [str(item.get("label") or "unknown") for item in type_items[:30]],
            },
        ]

        return sections, filters_out, sampled_records, source_count

    def generate_dashboard(self, sql_dashboard_service, filters: Optional[dict] = None, refresh: bool = False) -> dict:
        external_source_id, external_source_name = self._resolve_external_source(filters)
        if external_source_id and external_source_name:
            return self._build_runtime_only_dashboard(
                sql_dashboard_service,
                source_id=external_source_id,
                source_name=external_source_name,
                filters=filters,
            )

        sql_view = sql_dashboard_service.get_sql_dashboard(filters=filters, refresh=refresh)

        source_sections, source_filters, sampled_records, source_count = self._build_source_sections(filters)

        if sql_view.get("headline") == "No Data Available" and not source_sections:
            return sql_view

        if sql_view.get("headline") == "No Data Available" and source_sections:
            merged = {
                "data_context": {
                    "total_records": sampled_records,
                    "filtered_records": sampled_records,
                    "filters_applied": filters or {},
                },
                "headline": "Unified Knowledge Insights",
                "summary": (
                    f"Analyzed {sampled_records} records across {source_count} source(s) "
                    "from uploaded, built-in, and connected knowledge sources."
                ),
                "key_insights": [
                    "Insights include all first-class knowledge sources in the current runtime.",
                    "Use source and type filters to narrow to the exact data slice you want.",
                ],
                "standout_findings": [],
                "kpis": [
                    {"metric": "sampled_records", "label": "Sampled records", "value": sampled_records, "format": "number"},
                    {"metric": "source_count", "label": "Active sources", "value": source_count, "format": "number"},
                ],
                "sections": source_sections,
                "filters": source_filters,
                "suggested_questions": [
                    "Which source contributes most of the current data?",
                    "How is record volume distributed across source types?",
                ],
            }
            merged["runtime"] = sql_dashboard_service._to_runtime_payload(merged)
            return merged

        merged_sections = list(sql_view.get("sections", []))
        merged_sections.extend(source_sections)

        merged_filters = list(sql_view.get("filters", []))
        existing = {str(f.get("field")) for f in merged_filters if isinstance(f, dict)}
        for flt in source_filters:
            if flt["field"] not in existing:
                merged_filters.append(flt)

        key_insights = list(sql_view.get("key_insights", []))
        if source_count > 0:
            key_insights.append(
                f"Merged source coverage: {source_count} source(s), {sampled_records} sampled records."
            )

        merged = {
            **sql_view,
            "headline": "Unified Knowledge Insights",
            "summary": sql_view.get("summary") or "Insights across all active knowledge sources.",
            "sections": merged_sections,
            "filters": merged_filters,
            "key_insights": key_insights,
        }
        merged["runtime"] = sql_dashboard_service._to_runtime_payload(merged)
        return merged


analytics_engine = AnalyticsEngine()
