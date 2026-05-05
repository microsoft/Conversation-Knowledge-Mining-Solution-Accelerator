"""Insight engine: LLM proposes → system validates + structures → UI renders.

Key design:
  - LLM decides WHAT matters (insight_type + fields)
  - System VALIDATES the plan (field exists? values correct?)
  - SQL COMPUTES exact numbers
  - Response is fully structured with semantic info for downstream use

Response structure:
  - data_context:  total/filtered records, applied filters
  - kpis:          semantic KPIs with metric IDs and roles
  - sections:      typed sections with validated charts
  - filters:       structured with types (categorical, date_range, etc.)
  - suggested_questions: context-aware, referencing actual fields/values
"""

import json
import logging
import re
import struct
import hashlib
from collections import Counter

from src.api.config import get_settings
from src.api.capabilities._llm import get_llm_client

logger = logging.getLogger(__name__)
_SAFE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


# ═══════════════════════════════════════════════════
# Schema Extractor
# ═══════════════════════════════════════════════════

def _extract_schema(cursor) -> dict:
    cursor.execute("SELECT COUNT(*) FROM documents")
    total = cursor.fetchone()[0]

    cursor.execute(
        "SELECT TOP 150 metadata FROM documents "
        "WHERE metadata IS NOT NULL AND LEN(metadata) > 2"
    )
    field_info: dict[str, dict] = {}
    for row in cursor.fetchall():
        try:
            meta = json.loads(row[0])
            if not isinstance(meta, dict):
                continue
            for key, val in meta.items():
                if not _SAFE.match(key):
                    continue
                if key not in field_info:
                    field_info[key] = {"samples": set(), "count": 0}
                field_info[key]["count"] += 1
                if val is not None and str(val).strip() and len(field_info[key]["samples"]) < 20:
                    field_info[key]["samples"].add(str(val).strip())
        except (json.JSONDecodeError, TypeError):
            continue

    cursor.execute(
        "SELECT TOP 5 key_phrases FROM documents "
        "WHERE key_phrases IS NOT NULL AND LEN(key_phrases) > 2"
    )
    has_phrases = False
    for r in cursor.fetchall():
        try:
            if isinstance(json.loads(r[0]), list):
                has_phrases = True
                break
        except Exception:
            pass

    fields = [{"name": n, "unique_count": len(i["samples"]),
               "sample_values": list(i["samples"])[:10],
               "coverage": f"{i['count']}/{min(total, 150)}"}
              for n, i in field_info.items()]

    return {"total_records": total, "fields": fields, "has_key_phrases": has_phrases}


# ═══════════════════════════════════════════════════
# LLM Planner
# ═══════════════════════════════════════════════════

_PLAN_PROMPT = """You are a data analyst designing an insight dashboard.

DATASET SCHEMA:
{schema}

Return JSON with this structure:

{{
  "headline": "6-10 word use case headline",
  "summary": "One sentence (max 30 words) describing what this data represents",

  "kpis": [
    {{
      "metric": "unique_metric_id (e.g. total_records, satisfaction_rate, avg_duration)",
      "label": "Human-readable label",
      "role": "count | outcome | duration",
      "query_type": "count | rate | average_duration",
      "field": "metadata field (for rate)",
      "positive_value": "positive value (for rate)",
      "start_field": "start time field (for average_duration)",
      "end_field": "end time field (for average_duration)",
      "format": "number | percentage | minutes"
    }}
  ],

  "sections": [
    {{
      "id": "unique-id",
      "title": "Section title",
      "type": "summary | breakdown | trend | distribution | text_analysis | drivers",
      "charts": [
        {{
          "insight_type": "distribution | rate_by_dimension | duration_by_dimension | trend_over_time | top_phrases | trending_table",
          "title": "Chart title",
          "description": "One sentence: why this insight matters",
          "visualization": "donut | bar | horizontal_bar | line | table | word_cloud",
          "field": "primary field (for distribution/trending_table)",
          "outcome_field": "outcome field (for rate_by_dimension)",
          "positive_value": "positive value (for rate_by_dimension)",
          "dimension_field": "grouping field (for rate_by_dimension / duration_by_dimension)",
          "start_field": "start time field",
          "end_field": "end time field",
          "time_field": "time field (for trend_over_time)"
        }}
      ]
    }}
  ],

  "include_drivers": {{
    "outcome_field": "field",
    "outcome_label": "human label for the outcome",
    "positive_value": "positive value",
    "dimension_fields": ["field1", "field2", "field3"]
  }} or null,

  "filters": [
    {{
      "field": "field name",
      "label": "Human label",
      "type": "categorical | date_range",
      "multi_select": false
    }}
  ],

  "suggested_questions": ["question 1", "question 2", "question 3"]
}}

RULES:
- Only use field names from the schema
- 3-5 KPIs, 2-4 sections, each with 1-2 charts
- Section types must be one of: summary, breakdown, trend, distribution, text_analysis, drivers
- insight_type must match query_type exactly
- Suggested questions MUST reference actual field names or values from the schema
- Include drivers only if a clear binary outcome exists
- Include text_analysis only if has_key_phrases is true
- Include trend only if time fields exist
- Return ONLY valid JSON"""


def _plan(schema: dict) -> dict:
    settings = get_settings()
    client = get_llm_client()
    resp = client.chat.completions.create(
        model=settings.azure_openai_chat_deployment,
        messages=[{"role": "user", "content": _PLAN_PROMPT.format(
            schema=json.dumps(schema, indent=2, default=str))}],
        temperature=0.1, max_tokens=2500,
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {}


# ═══════════════════════════════════════════════════
# Plan Validator — catch bad LLM output
# ═══════════════════════════════════════════════════

def _validate_plan(plan: dict, schema: dict) -> dict:
    """Validate and fix the LLM plan against the actual schema."""
    known_fields = {f["name"] for f in schema.get("fields", [])}

    def _field_ok(f: str | None) -> bool:
        return bool(f and f in known_fields and _SAFE.match(f))

    # Validate KPIs
    valid_kpis = []
    for kpi in plan.get("kpis", []):
        qt = kpi.get("query_type", "")
        if qt == "count":
            valid_kpis.append(kpi)
        elif qt == "rate" and _field_ok(kpi.get("field")) and kpi.get("positive_value"):
            valid_kpis.append(kpi)
        elif qt == "average_duration" and _field_ok(kpi.get("start_field")) and _field_ok(kpi.get("end_field")):
            valid_kpis.append(kpi)
    plan["kpis"] = valid_kpis

    # Validate sections/charts
    valid_sections = []
    for sec in plan.get("sections", []):
        valid_charts = []
        for ch in sec.get("charts", []):
            it = ch.get("insight_type", "")
            ok = False
            if it == "distribution" and _field_ok(ch.get("field")):
                ok = True
            elif it == "rate_by_dimension" and _field_ok(ch.get("outcome_field")) and _field_ok(ch.get("dimension_field")):
                ok = True
            elif it == "duration_by_dimension" and _field_ok(ch.get("start_field")) and _field_ok(ch.get("end_field")) and _field_ok(ch.get("dimension_field")):
                ok = True
            elif it == "trend_over_time" and (_field_ok(ch.get("time_field")) or _field_ok(ch.get("start_field"))):
                ok = True
            elif it == "top_phrases" and schema.get("has_key_phrases"):
                ok = True
            elif it == "trending_table" and _field_ok(ch.get("field")):
                ok = True
            if ok:
                valid_charts.append(ch)
        if valid_charts:
            sec["charts"] = valid_charts
            valid_sections.append(sec)
    plan["sections"] = valid_sections

    # Validate drivers
    dc = plan.get("include_drivers")
    if dc:
        if not (_field_ok(dc.get("outcome_field")) and dc.get("positive_value")):
            plan["include_drivers"] = None
        else:
            dc["dimension_fields"] = [f for f in dc.get("dimension_fields", []) if _field_ok(f)]
            if not dc["dimension_fields"]:
                plan["include_drivers"] = None

    # Validate filters
    plan["filters"] = [f for f in plan.get("filters", []) if _field_ok(f.get("field"))]

    return plan


# ═══════════════════════════════════════════════════
# Query Engine
# ═══════════════════════════════════════════════════

def _build_where(filters: dict | None, params: list) -> str:
    clauses = ["1=1"]
    if filters:
        for field, value in filters.items():
            if _SAFE.match(field):
                clauses.append(f"JSON_VALUE(metadata, '$.{field}') = ?")
                params.append(value)
    return " AND ".join(clauses)


def _count_filtered(cursor, where, params) -> int:
    cursor.execute(f"SELECT COUNT(*) FROM documents WHERE {where}", list(params))
    return cursor.fetchone()[0]


def _exec_kpi(cursor, spec, where, params):
    qt = spec.get("query_type", "")
    base = {"label": spec["label"], "format": spec.get("format", "number"),
            "metric": spec.get("metric", ""), "role": spec.get("role", "")}
    try:
        if qt == "count":
            cursor.execute(f"SELECT COUNT(*) FROM documents WHERE {where}", list(params))
            return {**base, "value": cursor.fetchone()[0]}
        if qt == "rate":
            f, pos = spec["field"], spec["positive_value"]
            cursor.execute(
                f"SELECT SUM(CASE WHEN JSON_VALUE(metadata,'$.{f}')=? THEN 1 ELSE 0 END)*100.0"
                f"/NULLIF(COUNT(*),0) FROM documents WHERE {where} "
                f"AND JSON_VALUE(metadata,'$.{f}') IS NOT NULL",
                [pos] + list(params))
            r = cursor.fetchone()
            return {**base, "value": round(float(r[0]), 1) if r and r[0] else 0, "format": "percentage"}
        if qt == "average_duration":
            sf, ef = spec["start_field"], spec["end_field"]
            cursor.execute(
                f"SELECT AVG(DATEDIFF(MINUTE,TRY_CAST(JSON_VALUE(metadata,'$.{sf}') AS DATETIME2),"
                f"TRY_CAST(JSON_VALUE(metadata,'$.{ef}') AS DATETIME2))) "
                f"FROM documents WHERE {where} AND JSON_VALUE(metadata,'$.{sf}') IS NOT NULL "
                f"AND JSON_VALUE(metadata,'$.{ef}') IS NOT NULL", list(params))
            r = cursor.fetchone()
            return {**base, "value": round(float(r[0])) if r and r[0] else 0, "format": "minutes"}
    except Exception as e:
        logger.warning(f"KPI failed ({spec.get('label','')}): {e}")
    return None


def _exec_chart(cursor, spec, where, params):
    it = spec.get("insight_type", "")
    base = {"insight_type": it, "title": spec.get("title", ""),
            "description": spec.get("description", ""),
            "visualization": spec.get("visualization", "bar")}
    try:
        if it == "distribution":
            f = spec["field"]
            cursor.execute(
                f"SELECT JSON_VALUE(metadata,'$.{f}'),COUNT(*) FROM documents WHERE {where} "
                f"AND JSON_VALUE(metadata,'$.{f}') IS NOT NULL "
                f"GROUP BY JSON_VALUE(metadata,'$.{f}') ORDER BY COUNT(*) DESC", list(params))
            data = [{"label": r[0], "value": r[1]} for r in cursor.fetchall() if r[0]]
            return {**base, "data": data, "field": f} if len(data) >= 2 else None

        if it == "rate_by_dimension":
            of, df, pos = spec["outcome_field"], spec["dimension_field"], spec["positive_value"]
            cursor.execute(
                f"SELECT JSON_VALUE(metadata,'$.{df}'),"
                f"SUM(CASE WHEN JSON_VALUE(metadata,'$.{of}')=? THEN 1 ELSE 0 END),COUNT(*) "
                f"FROM documents WHERE {where} AND JSON_VALUE(metadata,'$.{df}') IS NOT NULL "
                f"GROUP BY JSON_VALUE(metadata,'$.{df}') ORDER BY COUNT(*) DESC",
                [pos] + list(params))
            data = [{"label": r[0], "value": round(r[1]*100.0/r[2], 1), "positive": r[1], "total": r[2]}
                    for r in cursor.fetchall() if r[0] and r[2] > 0]
            return {**base, "data": data} if len(data) >= 2 else None

        if it == "duration_by_dimension":
            sf, ef, df = spec["start_field"], spec["end_field"], spec["dimension_field"]
            cursor.execute(
                f"SELECT JSON_VALUE(metadata,'$.{df}'),"
                f"AVG(DATEDIFF(MINUTE,TRY_CAST(JSON_VALUE(metadata,'$.{sf}') AS DATETIME2),"
                f"TRY_CAST(JSON_VALUE(metadata,'$.{ef}') AS DATETIME2))) "
                f"FROM documents WHERE {where} AND JSON_VALUE(metadata,'$.{df}') IS NOT NULL "
                f"AND JSON_VALUE(metadata,'$.{sf}') IS NOT NULL AND JSON_VALUE(metadata,'$.{ef}') IS NOT NULL "
                f"GROUP BY JSON_VALUE(metadata,'$.{df}') ORDER BY 2 DESC", list(params))
            data = [{"label": r[0], "value": round(r[1]) if r[1] else 0} for r in cursor.fetchall() if r[0]]
            return {**base, "data": data} if data else None

        if it == "trend_over_time":
            tf = spec.get("time_field") or spec.get("start_field", "")
            cursor.execute(
                f"SELECT CAST(TRY_CAST(JSON_VALUE(metadata,'$.{tf}') AS DATE) AS NVARCHAR),COUNT(*) "
                f"FROM documents WHERE {where} AND JSON_VALUE(metadata,'$.{tf}') IS NOT NULL "
                f"GROUP BY CAST(TRY_CAST(JSON_VALUE(metadata,'$.{tf}') AS DATE) AS NVARCHAR) ORDER BY 1",
                list(params))
            data = [{"label": r[0], "value": r[1]} for r in cursor.fetchall() if r[0]]
            return {**base, "visualization": "line", "data": data} if len(data) >= 2 else None

        if it == "top_phrases":
            cursor.execute(
                f"SELECT key_phrases FROM documents WHERE {where} "
                f"AND key_phrases IS NOT NULL AND LEN(key_phrases)>2", list(params))
            ctr: Counter = Counter()
            for row in cursor.fetchall():
                try:
                    for p in json.loads(row[0]):
                        if isinstance(p, str) and len(p.strip()) > 1:
                            ctr[p.strip().lower()] += 1
                except Exception:
                    pass
            top = ctr.most_common(30)
            if not top:
                return None
            mx = top[0][1]
            return {**base, "visualization": "word_cloud",
                    "data": [{"text": t, "frequency": f, "weight": round(f/mx, 2)} for t, f in top]}

        if it == "trending_table":
            f = spec["field"]
            cursor.execute(
                f"SELECT JSON_VALUE(metadata,'$.{f}'),COUNT(*) FROM documents WHERE {where} "
                f"AND JSON_VALUE(metadata,'$.{f}') IS NOT NULL "
                f"GROUP BY JSON_VALUE(metadata,'$.{f}') ORDER BY COUNT(*) DESC", list(params))
            data = [{"label": r[0], "value": r[1]} for r in cursor.fetchall() if r[0]]
            return {**base, "visualization": "table", "data": data} if data else None
    except Exception as e:
        logger.warning(f"Chart failed ({spec.get('title','')}): {e}")
    return None


def _exec_drivers(cursor, config, where, params):
    of, pos = config["outcome_field"], config["positive_value"]
    dims = config.get("dimension_fields", [])
    o_label = config.get("outcome_label", of.replace("_", " ").title())
    try:
        cursor.execute(
            f"SELECT SUM(CASE WHEN JSON_VALUE(metadata,'$.{of}')=? THEN 1 ELSE 0 END)*100.0"
            f"/NULLIF(COUNT(*),0) FROM documents WHERE {where} "
            f"AND JSON_VALUE(metadata,'$.{of}') IS NOT NULL",
            [pos] + list(params))
        r = cursor.fetchone()
        if not r or r[0] is None:
            return None
        baseline = float(r[0])

        factors = []
        for dim in dims:
            cursor.execute(
                f"SELECT JSON_VALUE(metadata,'$.{dim}'),"
                f"SUM(CASE WHEN JSON_VALUE(metadata,'$.{of}')=? THEN 1 ELSE 0 END),COUNT(*) "
                f"FROM documents WHERE {where} AND JSON_VALUE(metadata,'$.{dim}') IS NOT NULL "
                f"GROUP BY JSON_VALUE(metadata,'$.{dim}') HAVING COUNT(*)>=3 ORDER BY COUNT(*) DESC",
                [pos] + list(params))
            for row in cursor.fetchall():
                if row[0] and row[2] > 0:
                    rate = round(row[1]*100.0/row[2], 1)
                    dev = round(rate - baseline, 1)
                    if abs(dev) >= 3:
                        factors.append({
                            "dimension": dim.replace("_", " ").title(), "value": row[0],
                            "rate": rate, "baseline": round(baseline, 1), "deviation": dev,
                            "impact": "positive" if dev > 0 else "negative", "count": row[2]})
        if not factors:
            return None
        factors.sort(key=lambda x: abs(x["deviation"]), reverse=True)
        worst = next((f for f in factors if f["impact"] == "negative"), None)
        best = next((f for f in factors if f["impact"] == "positive"), None)
        desc = ". ".join(filter(None, [
            f"{worst['value']} has the lowest {o_label.lower()} ({worst['rate']}%)" if worst else "",
            f"{best['value']} has the highest ({best['rate']}%)" if best else ""]))
        return {
            "insight_type": "drivers", "title": f"What Drives {o_label}?",
            "description": desc, "visualization": "driver_table",
            "data": {"baseline": round(baseline, 1), "outcome_label": o_label, "factors": factors[:15]}}
    except Exception as e:
        logger.warning(f"Drivers failed: {e}")
    return None


def _exec_filters(cursor, filter_specs):
    result = []
    for spec in filter_specs:
        f = spec.get("field", "")
        if not _SAFE.match(f):
            continue
        try:
            cursor.execute(
                f"SELECT DISTINCT JSON_VALUE(metadata,'$.{f}') FROM documents "
                f"WHERE JSON_VALUE(metadata,'$.{f}') IS NOT NULL ORDER BY 1")
            vals = [r[0] for r in cursor.fetchall() if r[0]]
            if 2 <= len(vals) <= 30:
                result.append({
                    "field": f,
                    "label": spec.get("label", f.replace("_", " ").title()),
                    "type": spec.get("type", "categorical"),
                    "multi_select": spec.get("multi_select", False),
                    "values": vals})
        except Exception:
            pass
    return result


# ═══════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════

class DashboardService:
    _plan_cache: dict[str, dict] = {}

    def _get_connection(self):
        settings = get_settings()
        if not settings.azure_sql_server:
            return None
        try:
            import pyodbc
            from azure.identity import DefaultAzureCredential
            cred = DefaultAzureCredential()
            tok = cred.get_token("https://database.windows.net/.default")
            tb = tok.token.encode("utf-16-le")
            ts = struct.pack(f"<I{len(tb)}s", len(tb), tb)
            return pyodbc.connect(
                f"Driver={{ODBC Driver 18 for SQL Server}};Server={settings.azure_sql_server};"
                f"Database={settings.azure_sql_database};Encrypt=yes;TrustServerCertificate=no;",
                attrs_before={1256: ts})
        except Exception as e:
            logger.warning(f"SQL connection failed: {e}")
            return None

    def get_dashboard(self, filters=None, refresh=False) -> dict:
        conn = self._get_connection()
        if not conn:
            return self._empty()
        try:
            cursor = conn.cursor()
            schema = _extract_schema(cursor)
            if schema["total_records"] == 0:
                conn.close()
                return self._empty()

            # Plan (cached, validated)
            key = hashlib.md5(json.dumps(schema, sort_keys=True, default=str).encode()).hexdigest()
            if refresh or key not in self._plan_cache:
                raw_plan = _plan(schema)
                self._plan_cache[key] = _validate_plan(raw_plan, schema)
            plan = self._plan_cache[key]
            if not plan:
                conn.close()
                return self._empty()

            # Build WHERE
            params: list = []
            where = _build_where(filters, params)
            filtered_count = _count_filtered(cursor, where, params)

            # Execute KPIs
            kpis = [r for s in plan.get("kpis", []) if (r := _exec_kpi(cursor, s, where, params))]

            # Execute sections
            sections = []
            for sec in plan.get("sections", []):
                charts = [r for ch in sec.get("charts", []) if (r := _exec_chart(cursor, ch, where, params))]
                if charts:
                    sections.append({
                        "id": sec.get("id", ""),
                        "title": sec.get("title", ""),
                        "type": sec.get("type", "summary"),
                        "charts": charts})

            # Drivers
            dc = plan.get("include_drivers")
            if dc:
                dr = _exec_drivers(cursor, dc, where, params)
                if dr:
                    sections.append({
                        "id": "drivers", "title": dr["title"],
                        "type": "drivers", "charts": [dr]})

            # Filters
            avail_filters = _exec_filters(cursor, plan.get("filters", []))

            conn.close()
            return {
                "data_context": {
                    "total_records": schema["total_records"],
                    "filtered_records": filtered_count,
                    "filters_applied": filters or {},
                },
                "headline": plan.get("headline", "Data Insights"),
                "summary": plan.get("summary", ""),
                "kpis": kpis,
                "sections": sections,
                "filters": avail_filters,
                "suggested_questions": plan.get("suggested_questions", []),
            }
        except Exception as e:
            logger.warning(f"Dashboard failed: {e}")
            try:
                conn.close()
            except Exception:
                pass
            return self._empty()

    @staticmethod
    def _empty():
        return {
            "data_context": {"total_records": 0, "filtered_records": 0, "filters_applied": {}},
            "headline": "No Data Available",
            "summary": "Upload documents or connect a data source to see insights.",
            "kpis": [], "sections": [], "filters": [], "suggested_questions": [],
        }


dashboard_service = DashboardService()
