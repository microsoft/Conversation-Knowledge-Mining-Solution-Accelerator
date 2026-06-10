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
# Semantic Field Classifier
# ═══════════════════════════════════════════════════

_SEMANTIC_RULES: list[tuple[re.Pattern, str, str]] = [
    # (pattern, semantic_type, business_role)
    (re.compile(r"(^id$|_id$|ticket|case_num|record)", re.I), "identifier", "reference"),
    (re.compile(r"(sentiment|satisfaction|outcome|result|resolution_status)", re.I), "outcome", "customer_experience"),
    (re.compile(r"(rating|score|nps|csat)", re.I), "metric", "customer_experience"),
    (re.compile(r"(duration|elapsed|time_spent|handle_time|resolution_time)", re.I), "duration", "operational"),
    (re.compile(r"(timestamp|created|updated|date|_at$|_time$|start_time|end_time)", re.I), "time", "temporal"),
    (re.compile(r"(agent|rep|employee|handler|assigned)", re.I), "actor", "workforce"),
    (re.compile(r"(customer|caller|user|client|contact)", re.I), "actor", "customer"),
    (re.compile(r"(category|type|topic|department|channel|reason|complaint|issue)", re.I), "category", "classification"),
    (re.compile(r"(region|location|city|state|country|site|branch)", re.I), "dimension", "geographic"),
    (re.compile(r"(priority|severity|urgency|level|tier)", re.I), "dimension", "operational"),
    (re.compile(r"(transcript|text|body|content|description|notes|summary)", re.I), "text", "content"),
    (re.compile(r"(name|title|label|subject)", re.I), "label", "descriptive"),
    (re.compile(r"(count|total|amount|quantity|num_)", re.I), "metric", "quantitative"),
    (re.compile(r"(email|phone|address|url)", re.I), "contact", "pii"),
]


def _classify_field(name: str, samples: set, count: int, total_sampled: int) -> dict:
    """Infer semantic type, data type, and business role from field name and values."""
    sample_list = list(samples)

    # Data type detection
    data_type = "categorical"
    if all(_is_numeric(v) for v in sample_list[:10] if v):
        data_type = "numeric"
    elif all(_is_datetime(v) for v in sample_list[:10] if v):
        data_type = "datetime"
    elif any(len(v) > 100 for v in sample_list[:5]):
        data_type = "text"

    # Semantic type from name patterns
    semantic_type = "dimension"
    business_role = "general"
    for pattern, sem, role in _SEMANTIC_RULES:
        if pattern.search(name):
            semantic_type = sem
            business_role = role
            break

    # Override: high cardinality text → text type
    if data_type == "categorical" and len(samples) > 15:
        if semantic_type not in ("time", "identifier"):
            semantic_type = "dimension"

    # Override: datetime detected → time
    if data_type == "datetime" and semantic_type == "dimension":
        semantic_type = "time"
        business_role = "temporal"

    return {
        "semantic_type": semantic_type,
        "data_type": data_type,
        "business_role": business_role,
        "cardinality": len(samples),
        "coverage": round(count / max(total_sampled, 1), 2),
    }


def _is_numeric(val: str) -> bool:
    try:
        float(val.replace(",", ""))
        return True
    except (ValueError, AttributeError):
        return False


def _is_datetime(val: str) -> bool:
    import re as _re
    return bool(_re.match(
        r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", val
    )) or bool(_re.match(
        r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}", val
    ))


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
    sampled = min(total, 150)
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
        except Exception as e:
            logger.debug(f"Skipping malformed key_phrases row: {e}")

    fields = []
    for name, info in field_info.items():
        classification = _classify_field(name, info["samples"], info["count"], sampled)
        fields.append({
            "name": name,
            "unique_count": len(info["samples"]),
            "sample_values": list(info["samples"])[:10],
            "coverage": f"{info['count']}/{sampled}",
            **classification,
        })

    return {"total_records": total, "fields": fields, "has_key_phrases": has_phrases}


# ═══════════════════════════════════════════════════
# LLM Planner
# ═══════════════════════════════════════════════════

_PLAN_PROMPT = """You are a data analyst designing an insight dashboard.

DATASET SCHEMA:
{schema}

Each field includes:
- semantic_type: identifier | outcome | metric | duration | time | actor | category | dimension | text | label | contact
- data_type: categorical | numeric | datetime | text
- business_role: customer_experience | operational | temporal | workforce | customer | classification | geographic | content | descriptive | quantitative | reference | pii | general
- cardinality: number of unique values
- coverage: fraction of records with this field (0.0 to 1.0)

Use semantic_type to guide insight design:
- outcome fields → KPIs (rate), driver analysis, donut charts
- time fields → trend_over_time (line charts)
- category/dimension fields → distribution, rate_by_dimension, filters
- duration fields → average_duration KPIs, duration_by_dimension
- actor fields → rate_by_dimension breakdown
- identifier/contact/pii fields → NEVER use in charts or filters
- text fields → skip (use key_phrases instead if available)

Return JSON with this structure:

{{
  "headline": "6-10 word use case headline",
  "summary": "One sentence (max 30 words) describing what this data represents",

  "key_insights": [
    "First major pattern or finding (one sentence)",
    "Second major pattern or finding (one sentence)",
    "Third major pattern or finding (one sentence)",
    "Fourth major pattern or finding (one sentence)"
  ],

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

  "suggested_questions": ["question 1", "question 2", "question 3"],

  "standout_findings": [
    "First notable standout observation (one sentence)",
    "Second notable standout observation (one sentence)",
    "Third notable standout observation (one sentence)"
  ]
}}

RULES:
- Only use field names from the schema
- Use semantic_type to pick the right insight_type for each field
- Use fields with coverage >= 0.5 for KPIs and charts; avoid low-coverage fields
- NEVER use identifier, contact, or pii fields in charts, KPIs, or filters
- Prefer outcome fields for rate KPIs and driver analysis
- Prefer time fields for trend_over_time; prefer category/dimension for distribution
- 3-5 KPIs, 2-4 sections, each with 1-2 charts
- key_insights: exactly 3-4 bullets summarizing the most important patterns in the data
- standout_findings: exactly 2-3 bullets highlighting what stands out or is unusual
- Section types must be one of: summary, breakdown, trend, distribution, text_analysis, drivers
- The FIRST chart in the first section should be the single most important visualization
- insight_type must match query_type exactly
- Suggested questions MUST reference actual field names or values from the schema
- Include drivers only if a clear outcome field (semantic_type=outcome) exists
- Include text_analysis only if has_key_phrases is true
- Include trend only if time fields exist

LABEL QUALITY RULES (critical for user clarity):
- KPI labels MUST be self-explanatory without seeing the data. Bad: "Sentiment Distribution: 55.9%". Good: "Positive Sentiment Rate"
- KPI labels should describe WHAT is being measured, not the chart type
- For rate KPIs, the label must include which value is being counted (e.g. "Positive Outcome Rate" not "Outcome Rate")
- Chart titles must describe the specific analysis, not generic categories (e.g. "Satisfaction by Topic" not "Rate by Dimension")
- Chart descriptions should explain why the insight matters to a decision-maker in plain language
- For driver analysis, outcome_label must be a clear phrase like "Customer Satisfaction" not a raw field name
- Avoid jargon, abbreviations, and raw field names in any user-facing label
- Each KPI must measure something distinct — no two KPIs should show the same metric differently
- For bar charts, if a field has more than 6 unique values, use horizontal_bar instead of bar
- Limit distribution and rate_by_dimension charts to the top 10 values — do not show all categories
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


def _confidence_level(sample_size: int, coverage: float = 1.0) -> str:
    """Compute confidence label from sample size and coverage."""
    if sample_size >= 50 and coverage >= 0.7:
        return "high"
    if sample_size >= 20 and coverage >= 0.4:
        return "medium"
    return "low"


def _exec_kpi(cursor, spec, where, params):
    qt = spec.get("query_type", "")
    base = {"label": spec["label"], "format": spec.get("format", "number"),
            "metric": spec.get("metric", ""), "role": spec.get("role", "")}
    try:
        if qt == "count":
            cursor.execute(f"SELECT COUNT(*) FROM documents WHERE {where}", list(params))
            val = cursor.fetchone()[0]
            return {**base, "value": val,
                    "confidence": _confidence_level(val), "sample_size": val}
        if qt == "rate":
            f, pos = spec["field"], spec["positive_value"]
            cursor.execute(
                f"SELECT SUM(CASE WHEN JSON_VALUE(metadata,'$.{f}')=? THEN 1 ELSE 0 END),"
                f"COUNT(*) FROM documents WHERE {where} "
                f"AND JSON_VALUE(metadata,'$.{f}') IS NOT NULL",
                [pos] + list(params))
            r = cursor.fetchone()
            n = r[1] if r else 0
            val = round(r[0] * 100.0 / n, 1) if r and n > 0 else 0
            return {**base, "value": val, "format": "percentage",
                    "confidence": _confidence_level(n), "sample_size": n}
        if qt == "average_duration":
            sf, ef = spec["start_field"], spec["end_field"]
            cursor.execute(
                f"SELECT AVG(DATEDIFF(MINUTE,TRY_CAST(JSON_VALUE(metadata,'$.{sf}') AS DATETIME2),"
                f"TRY_CAST(JSON_VALUE(metadata,'$.{ef}') AS DATETIME2))),COUNT(*) "
                f"FROM documents WHERE {where} AND JSON_VALUE(metadata,'$.{sf}') IS NOT NULL "
                f"AND JSON_VALUE(metadata,'$.{ef}') IS NOT NULL", list(params))
            r = cursor.fetchone()
            n = r[1] if r else 0
            return {**base, "value": round(float(r[0])) if r and r[0] else 0, "format": "minutes",
                    "confidence": _confidence_level(n), "sample_size": n}
    except Exception as e:
        logger.warning(f"KPI failed ({spec.get('label','')}): {e}")
    return None


def _exec_chart(cursor, spec, where, params):
    it = spec.get("insight_type", "")
    base = {"insight_type": it, "title": spec.get("title", ""),
            "description": spec.get("description", ""),
            "visualization": spec.get("visualization", "bar")}

    def _with_confidence(result: dict, sample_size: int, coverage: float = 1.0) -> dict:
        return {**result, "confidence": _confidence_level(sample_size, coverage),
                "sample_size": sample_size}

    try:
        if it == "distribution":
            f = spec["field"]
            cursor.execute(
                f"SELECT TOP 10 JSON_VALUE(metadata,'$.{f}'),COUNT(*) FROM documents WHERE {where} "
                f"AND JSON_VALUE(metadata,'$.{f}') IS NOT NULL "
                f"GROUP BY JSON_VALUE(metadata,'$.{f}') ORDER BY COUNT(*) DESC", list(params))
            data = [{"label": r[0], "value": r[1]} for r in cursor.fetchall() if r[0]]
            n = sum(d["value"] for d in data)
            if len(data) > 6:
                base["visualization"] = "horizontal_bar"
            return _with_confidence({**base, "data": data, "field": f}, n) if len(data) >= 2 else None

        if it == "rate_by_dimension":
            of, df, pos = spec["outcome_field"], spec["dimension_field"], spec["positive_value"]
            cursor.execute(
                f"SELECT TOP 10 JSON_VALUE(metadata,'$.{df}'),"
                f"SUM(CASE WHEN JSON_VALUE(metadata,'$.{of}')=? THEN 1 ELSE 0 END),COUNT(*) "
                f"FROM documents WHERE {where} AND JSON_VALUE(metadata,'$.{df}') IS NOT NULL "
                f"GROUP BY JSON_VALUE(metadata,'$.{df}') ORDER BY COUNT(*) DESC",
                [pos] + list(params))
            data = [{"label": r[0], "value": round(r[1]*100.0/r[2], 1), "positive": r[1], "total": r[2]}
                    for r in cursor.fetchall() if r[0] and r[2] > 0]
            n = sum(d["total"] for d in data)
            if len(data) > 6:
                base["visualization"] = "horizontal_bar"
            return _with_confidence({**base, "data": data}, n) if len(data) >= 2 else None

        if it == "duration_by_dimension":
            sf, ef, df = spec["start_field"], spec["end_field"], spec["dimension_field"]
            cursor.execute(
                f"SELECT JSON_VALUE(metadata,'$.{df}'),"
                f"AVG(DATEDIFF(MINUTE,TRY_CAST(JSON_VALUE(metadata,'$.{sf}') AS DATETIME2),"
                f"TRY_CAST(JSON_VALUE(metadata,'$.{ef}') AS DATETIME2))),COUNT(*) "
                f"FROM documents WHERE {where} AND JSON_VALUE(metadata,'$.{df}') IS NOT NULL "
                f"AND JSON_VALUE(metadata,'$.{sf}') IS NOT NULL AND JSON_VALUE(metadata,'$.{ef}') IS NOT NULL "
                f"GROUP BY JSON_VALUE(metadata,'$.{df}') ORDER BY 2 DESC", list(params))
            data = [{"label": r[0], "value": round(r[1]) if r[1] else 0} for r in cursor.fetchall() if r[0]]
            n = sum(1 for _ in data)
            return _with_confidence({**base, "data": data}, n) if data else None

        if it == "trend_over_time":
            tf = spec.get("time_field") or spec.get("start_field", "")
            cursor.execute(
                f"SELECT CAST(TRY_CAST(JSON_VALUE(metadata,'$.{tf}') AS DATE) AS NVARCHAR),COUNT(*) "
                f"FROM documents WHERE {where} AND JSON_VALUE(metadata,'$.{tf}') IS NOT NULL "
                f"GROUP BY CAST(TRY_CAST(JSON_VALUE(metadata,'$.{tf}') AS DATE) AS NVARCHAR) ORDER BY 1",
                list(params))
            data = [{"label": r[0], "value": r[1]} for r in cursor.fetchall() if r[0]]
            n = sum(d["value"] for d in data)
            return _with_confidence({**base, "visualization": "line", "data": data}, n) if len(data) >= 2 else None

        if it == "top_phrases":
            cursor.execute(
                f"SELECT key_phrases FROM documents WHERE {where} "
                f"AND key_phrases IS NOT NULL AND LEN(key_phrases)>2", list(params))
            ctr: Counter = Counter()
            doc_count = 0
            for row in cursor.fetchall():
                doc_count += 1
                try:
                    for p in json.loads(row[0]):
                        if isinstance(p, str) and len(p.strip()) > 1:
                            ctr[p.strip().lower()] += 1
                except Exception as e:
                    logger.debug(f"Skipping malformed key_phrases in chart computation: {e}")
            top = ctr.most_common(15)
            if not top:
                return None
            mx = top[0][1]
            return _with_confidence(
                {**base, "visualization": "word_cloud",
                 "data": [{"text": t, "frequency": f, "weight": round(f/mx, 2)} for t, f in top]},
                doc_count)

        if it == "trending_table":
            f = spec["field"]
            cursor.execute(
                f"SELECT JSON_VALUE(metadata,'$.{f}'),COUNT(*) FROM documents WHERE {where} "
                f"AND JSON_VALUE(metadata,'$.{f}') IS NOT NULL "
                f"GROUP BY JSON_VALUE(metadata,'$.{f}') ORDER BY COUNT(*) DESC", list(params))
            data = [{"label": r[0], "value": r[1]} for r in cursor.fetchall() if r[0]]
            n = sum(d["value"] for d in data)
            return _with_confidence({**base, "visualization": "table", "data": data}, n) if data else None
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
        except Exception as e:
            logger.warning(f"Failed to load filter values for field '{f}': {e}")
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
                "key_insights": plan.get("key_insights", []),
                "standout_findings": plan.get("standout_findings", []),
                "kpis": kpis,
                "sections": sections,
                "filters": avail_filters,
                "suggested_questions": plan.get("suggested_questions", []),
            }
        except Exception as e:
            logger.warning(f"Dashboard failed: {e}")
            try:
                conn.close()
            except Exception as e:
                logger.debug(f"Failed to close connection after dashboard error: {e}")
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
