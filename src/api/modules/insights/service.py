"""Insight engine: LLM proposes insights, system validates and structures them for UI rendering."""

import json
import logging
import re
import struct
import hashlib
from datetime import datetime, timezone
from collections import Counter

from src.api.config import get_settings
from src.api.capabilities._llm import get_llm_client

logger = logging.getLogger(__name__)
_SAFE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_FILTER_BLOCKLIST = {"page_count", "pagecount", "pages", "page"}

# --- Semantic Field Classifier ---

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
    return bool(re.match(
        r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", val
    )) or bool(re.match(
        r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}", val
    ))


# --- Schema Extractor ---

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

    # Pull actual document summaries so the LLM can generate content-based insights
    cursor.execute(
        "SELECT TOP 15 summary FROM documents "
        "WHERE summary IS NOT NULL AND LEN(summary) > 20"
    )
    document_summaries = []
    for r in cursor.fetchall():
        if r[0] and r[0].strip():
            document_summaries.append(r[0].strip()[:600])

    # Aggregate key phrases across all documents for the planner
    cursor.execute(
        "SELECT TOP 30 key_phrases FROM documents "
        "WHERE key_phrases IS NOT NULL AND LEN(key_phrases) > 2"
    )
    phrase_pool: list[str] = []
    for r in cursor.fetchall():
        try:
            phrases = json.loads(r[0])
            if isinstance(phrases, list):
                phrase_pool.extend(p.strip().lower() for p in phrases[:15] if isinstance(p, str) and len(p.strip()) > 2)
        except Exception:
            continue

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

    return {
        "total_records": total,
        "fields": fields,
        "has_key_phrases": has_phrases,
        "document_summaries": document_summaries,
        "top_key_phrases": list(dict.fromkeys(phrase_pool))[:60],  # deduplicated
    }


# --- LLM Planner ---

_PLAN_PROMPT = """You are a data analyst designing an insight dashboard.

{content_section}
DATASET SCHEMA (structural metadata fields):
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

CONTENT-FIRST & ANONYMIZATION RULES (CRITICAL):
- If DOCUMENT SUMMARIES are provided above, the headline, summary, key_insights and standout_findings MUST reflect the actual subject matter of those documents — what they discuss, what findings they contain, what decisions or topics they cover.
- NEVER write key_insights that describe file format distributions (e.g. "PDFs are the most common file type") — that is not useful to users.
- NEVER write key_insights about page counts, processing metadata, or document structure unless the data explicitly measures those things meaningfully.
- The headline must describe the TOPIC of the content (e.g. "Non-Performing Loan Sales and Borrower Outcomes") not the collection type ("Document Processing Insights").
- For document collections (uploaded files), lean on the summaries to identify themes, findings, entities, geographies, time periods, and outcomes that actually appear in the content.
- Only use structural metadata fields (like file_format or document_type) in charts or filters if there are 4+ documents with real variation; even then, treat them as secondary to content insights.
- ANONYMIZATION (MANDATORY): NEVER include individual customer/person/employee names anywhere in headline, summary, or key_insights. Replace all individual names with organizational/domain names (e.g. "Woodgrove IT Helpdesk Support Requests" not "Helena's IT Support"). If the data is about customer interactions, use the organization/service name as context. All insights must be institutional/organizational in scope, never individual.


{{
  "headline": "6-10 word organizational/institutional headline (NO individual names, e.g. 'Woodgrove IT Helpdesk Support Interactions')",
  "summary": "One sentence (max 30 words) describing organizational/institutional context (NO individual names, focus on organization/system/domain)",

  "key_insights": [
    "First major pattern or finding (one sentence, organizational scope, NO individual names)",
    "Second major pattern or finding (one sentence, organizational scope, NO individual names)",
    "Third major pattern or finding (one sentence, organizational scope, NO individual names)",
    "Fourth major pattern or finding (one sentence, organizational scope, NO individual names)"
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
- Filters MUST be orthogonal (independent) — NEVER include fields that measure the same concept (e.g. sentiment and satisfaction both measure customer perception — pick ONE). A good filter set slices data along completely different axes (e.g. time + agent + category)
- NEVER use topic, key_phrases, or high-cardinality text fields as filters — they have too many values and belong in charts (word_cloud, horizontal_bar), not filters
- Always include a time-based filter if ANY time/datetime field exists in the schema (type: "date_range")
- Choose 2-4 filters total: 1 time filter (if available) + 1-3 categorical filters on low-cardinality independent dimensions
- Filters must work well both individually and combined — each filter should meaningfully narrow the data
- Return ONLY valid JSON"""


_NAME_STOPWORDS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
    "windows", "laptop", "printer", "scanner", "wifi", "network", "helpdesk", "support", "service", "team",
}


def _infer_org_label(schema: dict) -> str:
    summaries = schema.get("document_summaries") or []
    patterns = [
        r"([A-Z][A-Za-z0-9&\-]*(?:\s+[A-Z][A-Za-z0-9&\-]*){0,5}\s+(?:Helpdesk|Support|Service|Department|Center|Desk))",
        r"([A-Z][A-Za-z0-9&\-]*(?:\s+[A-Z][A-Za-z0-9&\-]*){0,5}\s+Contact Center)",
        r"([A-Z][A-Za-z0-9&\-]*(?:\s+[A-Z][A-Za-z0-9&\-]*){0,5}\s+Customer Service)",
    ]
    for summary in summaries:
        if not isinstance(summary, str):
            continue
        for p in patterns:
            m = re.search(p, summary)
            if m:
                return m.group(1).strip()
    return "the organization"


def _collect_person_tokens(schema: dict) -> set[str]:
    names: set[str] = set()
    for field in schema.get("fields", []):
        if not isinstance(field, dict):
            continue
        sem = str(field.get("semantic_type") or "").lower()
        role = str(field.get("business_role") or "").lower()
        if sem not in ("actor", "label"):
            continue
        if role not in ("customer", "workforce", "descriptive"):
            continue
        for raw in field.get("sample_values", []) or []:
            if not isinstance(raw, str):
                continue
            for tok in re.findall(r"\b[A-Z][a-z]{2,}\b", raw):
                if tok.lower() not in _NAME_STOPWORDS:
                    names.add(tok)

    for summary in schema.get("document_summaries", []) or []:
        if not isinstance(summary, str):
            continue
        for tok in re.findall(r"\b([A-Z][a-z]{2,})'s\b", summary):
            if tok.lower() not in _NAME_STOPWORDS:
                names.add(tok)
        for tok in re.findall(
            r"\b([A-Z][a-z]{2,})\s+(?:contacted|requested|reported|called|experienced|faced|raised|encountered|asked|needed|had)\b",
            summary,
            flags=re.IGNORECASE,
        ):
            if tok.lower() not in _NAME_STOPWORDS:
                names.add(tok)
    return names


def _collect_person_tokens_from_response(response: dict, org_label: str) -> set[str]:
    tokens: set[str] = set()
    corpus_parts = [
        response.get("headline", ""),
        response.get("summary", ""),
        * (response.get("key_insights") or []),
        * (response.get("standout_findings") or []),
    ]
    corpus = "\n".join(str(p) for p in corpus_parts if isinstance(p, str))

    for tok in re.findall(r"\b([A-Z][a-z]{2,})'s\b", corpus):
        if tok.lower() not in _NAME_STOPWORDS:
            tokens.add(tok)
    for tok in re.findall(
        r"\b(?:by|from)\s+([A-Z][a-z]{2,})\b|\b([A-Z][a-z]{2,})\s+(?:frequently|consistently|contacted|requested|reported|expressed|raised|experienced)\b",
        corpus,
        flags=re.IGNORECASE,
    ):
        candidate = tok[0] or tok[1]
        if candidate and candidate.lower() not in _NAME_STOPWORDS:
            tokens.add(candidate)

    org_words = {w for w in re.findall(r"\b[A-Za-z]{3,}\b", org_label)}
    return {t for t in tokens if t not in org_words}


def _anonymize_text(text: str, person_tokens: set[str], org_label: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return text

    out = text
    for token in sorted(person_tokens, key=len, reverse=True):
        out = re.sub(rf"\b{re.escape(token)}['’]s\b", f"{org_label}'s", out)
        out = re.sub(rf"\b{re.escape(token)}\b", "users", out)

    out = re.sub(
        rf"\b{re.escape(org_label)}['’]s interactions? with (?:the )?{re.escape(org_label)}\b",
        f"{org_label} support interactions",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _apply_anonymization(response: dict, schema: dict) -> dict:
    person_tokens = _collect_person_tokens(schema)
    org_label = _infer_org_label(schema)
    if not person_tokens:
        person_tokens = _collect_person_tokens_from_response(response, org_label)
    if not person_tokens:
        return response

    response["headline"] = _anonymize_text(response.get("headline", ""), person_tokens, org_label)
    response["summary"] = _anonymize_text(response.get("summary", ""), person_tokens, org_label)
    response["key_insights"] = [
        _anonymize_text(s, person_tokens, org_label) for s in (response.get("key_insights") or [])
    ]
    response["standout_findings"] = [
        _anonymize_text(s, person_tokens, org_label) for s in (response.get("standout_findings") or [])
    ]
    response["suggested_questions"] = [
        _anonymize_text(s, person_tokens, org_label) for s in (response.get("suggested_questions") or [])
    ]
    return response


def _plan(schema: dict) -> dict:
    settings = get_settings()
    client = get_llm_client()

    # Build content section from actual document summaries and key phrases
    content_parts: list[str] = []
    summaries = schema.get("document_summaries", [])
    if summaries:
        numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(summaries))
        content_parts.append(f"DOCUMENT SUMMARIES (actual content of the uploaded documents):\n{numbered}")
    phrases = schema.get("top_key_phrases", [])
    if phrases:
        content_parts.append(f"KEY PHRASES ACROSS ALL DOCUMENTS:\n{', '.join(phrases[:50])}")
    content_section = ("\n\n".join(content_parts) + "\n\n") if content_parts else ""

    # Strip large content fields from schema before serialising to keep prompt compact
    schema_for_prompt = {k: v for k, v in schema.items() if k not in ("document_summaries", "top_key_phrases")}

    resp = client.chat.completions.create(
        model=settings.azure_openai_chat_deployment,
        messages=[{"role": "user", "content": _PLAN_PROMPT.format(
            content_section=content_section,
            schema=json.dumps(schema_for_prompt, indent=2, default=str))}],
        temperature=0.1, max_tokens=2500,
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {}


# --- Plan Validator ---

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
    def _is_allowed_filter_field(field_name: str | None) -> bool:
        f = str(field_name or "").strip().lower().replace(" ", "_")
        return bool(f) and f not in _FILTER_BLOCKLIST and _field_ok(field_name)

    plan["filters"] = [f for f in plan.get("filters", []) if _is_allowed_filter_field(f.get("field"))]

    return plan


# --- Query Engine ---

def _build_where(filters: dict | None, params: list) -> str:
    clauses = ["1=1"]
    if filters:
        for field, value in filters.items():
            normalized = str(field or "").strip().lower().replace(" ", "_")
            if normalized in _FILTER_BLOCKLIST:
                continue
            # Year filter (virtual field: realfield__year)
            if field.endswith("__year"):
                real = field[:-6]
                if real.strip().lower().replace(" ", "_") in _FILTER_BLOCKLIST:
                    continue
                if _SAFE.match(real):
                    clauses.append(
                        f"YEAR(TRY_CAST(JSON_VALUE(metadata, '$.{real}') AS DATE)) = ?")
                    params.append(int(value))
            # Month filter (virtual field: realfield__month)
            elif field.endswith("__month"):
                real = field[:-7]
                if real.strip().lower().replace(" ", "_") in _FILTER_BLOCKLIST:
                    continue
                if _SAFE.match(real):
                    clauses.append(
                        f"FORMAT(TRY_CAST(JSON_VALUE(metadata, '$.{real}') AS DATE), 'MMMM') = ?")
                    params.append(value)
            elif _SAFE.match(field):
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
        logger.warning(f"KPI failed ({spec.get('label', '')}): {e}")
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
            data = [{"label": r[0], "value": round(r[1] * 100.0 / r[2], 1), "positive": r[1], "total": r[2]}
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
                 "data": [{"text": t, "frequency": f, "weight": round(f / mx, 2)} for t, f in top]},
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
        logger.warning(f"Chart failed ({spec.get('title', '')}): {e}")
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
                    rate = round(row[1] * 100.0 / row[2], 1)
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
        if str(f).strip().lower().replace(" ", "_") in _FILTER_BLOCKLIST:
            continue
        if not _SAFE.match(f):
            continue
        ftype = spec.get("type", "categorical")
        try:
            if ftype == "date_range":
                # Generate Year and Month dropdowns from actual data
                cursor.execute(
                    f"SELECT DISTINCT YEAR(TRY_CAST(JSON_VALUE(metadata,'$.{f}') AS DATE)) "
                    f"FROM documents WHERE JSON_VALUE(metadata,'$.{f}') IS NOT NULL "
                    f"AND TRY_CAST(JSON_VALUE(metadata,'$.{f}') AS DATE) IS NOT NULL "
                    f"ORDER BY 1 DESC")
                years = [str(r[0]) for r in cursor.fetchall() if r[0]]
                if years:
                    result.append({
                        "field": f + "__year",
                        "label": "Year",
                        "type": "year",
                        "multi_select": False,
                        "values": years})

                cursor.execute(
                    f"SELECT DISTINCT MONTH(TRY_CAST(JSON_VALUE(metadata,'$.{f}') AS DATE)), "
                    f"FORMAT(TRY_CAST(JSON_VALUE(metadata,'$.{f}') AS DATE), 'MMMM') "
                    f"FROM documents WHERE JSON_VALUE(metadata,'$.{f}') IS NOT NULL "
                    f"AND TRY_CAST(JSON_VALUE(metadata,'$.{f}') AS DATE) IS NOT NULL "
                    f"ORDER BY 1")
                months = [r[1] for r in cursor.fetchall() if r[0] and r[1]]
                if len(months) >= 2:
                    result.append({
                        "field": f + "__month",
                        "label": "Month",
                        "type": "month",
                        "multi_select": False,
                        "values": months})
            else:
                cursor.execute(
                    f"SELECT DISTINCT JSON_VALUE(metadata,'$.{f}') FROM documents "
                    f"WHERE JSON_VALUE(metadata,'$.{f}') IS NOT NULL ORDER BY 1")
                vals = [r[0] for r in cursor.fetchall() if r[0]]
                if 2 <= len(vals) <= 30:
                    result.append({
                        "field": f,
                        "label": spec.get("label", f.replace("_", " ").title()),
                        "type": "categorical",
                        "multi_select": spec.get("multi_select", False),
                        "values": vals})
        except Exception as e:
            logger.warning(f"Failed to load filter values for field '{f}': {e}")
    return result


def _to_runtime_payload(payload: dict) -> dict:
    """Adapt dashboard response fields into the runtime contract expected by the UI."""

    def _num(v, default=0.0) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return float(default)

    def _kpi_trend_direction(v) -> str:
        t = str(v or "").strip().lower()
        if t in ("up", "increase", "increasing", "rising"):
            return "up"
        if t in ("down", "decrease", "decreasing", "falling"):
            return "down"
        return "stable"

    # KPIs
    runtime_kpis = []
    for i, k in enumerate(payload.get("kpis", []) or []):
        if not isinstance(k, dict):
            continue
        runtime_kpis.append({
            "id": str(k.get("metric") or f"kpi_{i + 1}"),
            "label": str(k.get("label") or "KPI"),
            "value": k.get("value", 0),
            "format": k.get("format") or "number",
            "trendDirection": _kpi_trend_direction(k.get("trend")),
            "trendValue": None,
            "confidence": None,
        })

    # Topics / entities inferred from chart payloads
    topics_map: dict[str, float] = {}
    entities_map: dict[str, float] = {}
    relationships = []

    for sec in payload.get("sections", []) or []:
        if not isinstance(sec, dict):
            continue
        for ch in sec.get("charts", []) or []:
            if not isinstance(ch, dict):
                continue

            vis = str(ch.get("visualization") or "").lower()
            insight_type = str(ch.get("insight_type") or "").lower()
            field_name = str(ch.get("field") or "").lower()
            title = str(ch.get("title") or "").lower()
            is_topic_like = (
                vis == "word_cloud"
                or any(t in field_name for t in ("topic", "theme", "phrase", "keyword"))
                or any(t in title for t in ("topic", "theme", "phrase", "keyword"))
            )

            data = ch.get("data")
            if isinstance(data, list):
                for row in data:
                    if not isinstance(row, dict):
                        continue

                    if vis == "word_cloud":
                        name = str(row.get("text") or "").strip()
                        score = _num(row.get("frequency") or row.get("weight") or 0)
                        if name:
                            topics_map[name] = topics_map.get(name, 0.0) + max(score, 0.0)
                        continue

                    label = str(row.get("label") or "").strip()
                    if not label:
                        continue
                    value = max(_num(row.get("value"), 0.0), 0.0)

                    if is_topic_like:
                        topics_map[label] = topics_map.get(label, 0.0) + value
                    else:
                        entities_map[label] = entities_map.get(label, 0.0) + value

            # Driver charts can be converted into lightweight relationship edges
            if insight_type == "drivers" and isinstance(data, dict):
                outcome_label = str(data.get("outcome_label") or "outcome")
                for f in data.get("factors", []) or []:
                    if not isinstance(f, dict):
                        continue
                    dim = str(f.get("dimension") or "Factor").strip()
                    val = str(f.get("value") or "").strip()
                    if not dim or not val:
                        continue
                    relationships.append({
                        "from": dim,
                        "to": val,
                        "relation": f"affects {outcome_label}",
                        "strength": max(abs(_num(f.get("deviation"), 0.0)), 0.1),
                    })

    topics = [
        {"id": f"topic_{i + 1}", "name": name, "score": round(score, 2), "trendValue": None, "trendDirection": "stable"}
        for i, (name, score) in enumerate(
            sorted(topics_map.items(), key=lambda x: x[1], reverse=True)[:30]
        )
    ]

    entities = [
        {
            "id": f"entity_{i + 1}",
            "name": name,
            "mentions": int(round(count)),
            "trendDirection": "stable",
            "trendValue": None,
        }
        for i, (name, count) in enumerate(
            sorted(entities_map.items(), key=lambda x: x[1], reverse=True)[:30]
        )
    ]

    # Insights derived from planner text outputs
    def _insight_category(text: str) -> str:
        t = text.lower()
        if "risk" in t or "concern" in t:
            return "Risk"
        if "anomaly" in t or "unusual" in t or "spike" in t or "drop" in t:
            return "Anomaly"
        if "opportun" in t or "potential" in t:
            return "Opportunity"
        if "trend" in t or "increas" in t or "decreas" in t:
            return "Trend"
        return "Insight"

    insights = []
    key_insights = payload.get("key_insights", []) or []
    standout = payload.get("standout_findings", []) or []
    for i, text in enumerate([*key_insights, *standout]):
        if not isinstance(text, str) or not text.strip():
            continue
        category = _insight_category(text)
        insights.append({
            "id": f"insight_{i + 1}",
            "category": category,
            "title": text.strip(),
            "confidence": None,
            "impactScore": 0.8 if category in ("Risk", "Anomaly") else 0.7,
            "context": payload.get("headline", ""),
            "explanation": payload.get("summary", ""),
            "evidenceCount": 0,
            "evidence": [],
        })

    unexpected_patterns = []
    for i, text in enumerate(standout):
        if not isinstance(text, str) or not text.strip():
            continue
        lower = text.lower()
        is_high = any(tok in lower for tok in ("risk", "anomaly", "spike", "drop", "critical"))
        unexpected_patterns.append({
            "id": f"pattern_{i + 1}",
            "pattern": text.strip(),
            "severity": "high" if is_high else "medium",
            "explanation": payload.get("summary", "Observed in the analyzed records."),
        })

    actions = [
        {"id": f"action_{i + 1}", "label": q.strip(), "intentType": "explore"}
        for i, q in enumerate(payload.get("suggested_questions", []) or [])
        if isinstance(q, str) and q.strip()
    ]

    data_context = payload.get("data_context", {}) or {}
    record_count = int(data_context.get("filtered_records") or data_context.get("total_records") or 0)

    summary_signals = []
    if payload.get("headline"):
        summary_signals.append(str(payload["headline"]))
    summary_signals.extend([s for s in key_insights if isinstance(s, str)])

    return {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "recordCount": record_count,
        "counts": {
            "topics": len(topics),
            "entities": len(entities),
            "relationships": len(relationships),
        },
        "summarySignals": summary_signals[:6],
        "kpis": runtime_kpis,
        "topics": topics,
        "entities": entities,
        "relationships": relationships[:20],
        "insights": insights,
        "unexpectedPatterns": unexpected_patterns,
        "actions": actions,
    }


def _parse_entity_values(raw) -> list[str]:
    names: list[str] = []
    if raw is None:
        return names

    value = raw
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return names
        try:
            value = json.loads(text)
        except Exception:
            # Fallback for comma-separated strings
            return [p.strip() for p in text.split(",") if p and p.strip()]

    if isinstance(value, dict):
        candidate = value.get("name") or value.get("label") or value.get("text")
        if isinstance(candidate, str) and candidate.strip():
            names.append(candidate.strip())
        return names

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                names.append(item.strip())
            elif isinstance(item, dict):
                candidate = item.get("name") or item.get("label") or item.get("text")
                if isinstance(candidate, str) and candidate.strip():
                    names.append(candidate.strip())
    return names


def _runtime_entities_from_documents(cursor, where: str, params: list, limit: int = 30) -> list[dict]:
    """Fallback entity extraction from document rows when chart-derived entities are empty."""
    counter: Counter = Counter()
    try:
        cursor.execute(
            f"SELECT TOP 500 entities, metadata FROM documents WHERE {where}",
            list(params),
        )
        for row in cursor.fetchall():
            entities_col = row[0] if len(row) > 0 else None
            metadata_col = row[1] if len(row) > 1 else None

            for name in _parse_entity_values(entities_col):
                counter[name] += 1

            if metadata_col:
                try:
                    meta = json.loads(metadata_col) if isinstance(metadata_col, str) else metadata_col
                    if isinstance(meta, dict):
                        for name in _parse_entity_values(meta.get("entities")):
                            counter[name] += 1
                except Exception:
                    continue
    except Exception as e:
        logger.debug(f"Entity fallback query failed: {e}")
        return []

    if not counter:
        return []

    entities = []
    for i, (name, count) in enumerate(counter.most_common(limit)):
        entities.append({
            "id": f"entity_fallback_{i + 1}",
            "name": name,
            "mentions": int(count),
            "trendDirection": "stable",
            "trendValue": None,
        })
    return entities


# --- Orchestrator ---

class DashboardService:
    _plan_cache: dict[str, dict] = {}
    _plan_cache_ts: dict[str, float] = {}
    _schema_cache: dict | None = None
    _schema_hash: str | None = None
    _CACHE_TTL_SEC = 3600  # 1 hour

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

    @staticmethod
    def _get_total_records(cursor) -> int:
        cursor.execute("SELECT COUNT(*) FROM documents")
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def get_dashboard(self, filters=None, refresh=False) -> dict:
        conn = self._get_connection()
        if not conn:
            return self._empty()
        try:
            cursor = conn.cursor()

            # Schema: refresh when requested or when source data count changed.
            if refresh or self._schema_cache is None:
                schema = _extract_schema(cursor)
                if schema["total_records"] == 0:
                    conn.close()
                    return self._empty()
                self._schema_cache = schema
                self._schema_hash = hashlib.md5(
                    json.dumps(schema, sort_keys=True, default=str).encode()
                ).hexdigest()
            else:
                live_total = self._get_total_records(cursor)
                cached_total = int(self._schema_cache.get("total_records", 0))
                if live_total != cached_total:
                    schema = _extract_schema(cursor)
                    if schema["total_records"] == 0:
                        conn.close()
                        return self._empty()
                    self._schema_cache = schema
                    self._schema_hash = hashlib.md5(
                        json.dumps(schema, sort_keys=True, default=str).encode()
                    ).hexdigest()
                else:
                    schema = self._schema_cache

            # Plan (cached, validated, with TTL)
            key = self._schema_hash
            import time
            cache_expired = (key in self._plan_cache_ts
                             and time.time() - self._plan_cache_ts.get(key, 0) > self._CACHE_TTL_SEC)
            if refresh or key not in self._plan_cache or cache_expired:
                raw_plan = _plan(schema)
                self._plan_cache[key] = _validate_plan(raw_plan, schema)
                self._plan_cache_ts[key] = time.time()
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

            response = {
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
            response = _apply_anonymization(response, schema)
            response["runtime"] = _to_runtime_payload(response)

            runtime = response.get("runtime") or {}
            counts = runtime.get("counts") if isinstance(runtime, dict) else None
            current_entity_count = 0
            if isinstance(counts, dict):
                current_entity_count = int(counts.get("entities") or 0)
            if current_entity_count == 0:
                fallback_entities = _runtime_entities_from_documents(cursor, where, params)
                if fallback_entities:
                    runtime["entities"] = fallback_entities
                    runtime.setdefault("counts", {})
                    runtime["counts"]["entities"] = len(fallback_entities)
            return response
        except Exception as e:
            logger.warning(f"Dashboard failed: {e}")
            try:
                conn.close()
            except Exception as e:
                logger.debug(f"Failed to close connection after dashboard error: {e}")
            return self._empty()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def _empty():
        response = {
            "data_context": {"total_records": 0, "filtered_records": 0, "filters_applied": {}},
            "headline": "No Data Available",
            "summary": "Upload documents or connect a data source to see insights.",
            "kpis": [], "sections": [], "filters": [], "suggested_questions": [],
        }
        response["runtime"] = _to_runtime_payload(response)
        return response


dashboard_service = DashboardService()
