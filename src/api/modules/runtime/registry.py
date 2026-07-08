from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any, Optional

logger = logging.getLogger(__name__)


class UnifiedDataSourceRegistry:
    """Unified runtime access across uploaded, seeded, and connected external sources."""

    @staticmethod
    def _normalize_signature_part(value: Any) -> str:
        return str(value or "").strip().lower()

    def _source_quality_score(self, cfg: Any) -> float:
        """Prefer stable, human-friendly names when duplicate connections exist."""
        name = str(getattr(cfg, "name", "") or "").strip()
        source_type_raw = getattr(cfg, "source_type", "")
        source_type = source_type_raw.value if hasattr(source_type_raw, "value") else str(source_type_raw or "")
        lowered = name.lower()
        mapping = getattr(cfg, "field_mapping", None)
        text_field = str(getattr(mapping, "text_field", "") or "").strip().lower()
        title_field = str(getattr(mapping, "title_field", "") or "").strip().lower()
        metadata_fields = getattr(mapping, "metadata_fields", {}) or {}

        score = 0.0
        if lowered and lowered != source_type.lower():
            score += 2.0
        if "test" not in lowered:
            score += 2.0
        if "endpoint" not in lowered:
            score += 1.0
        if lowered and any(ch in lowered for ch in ("-", "_")):
            score += 0.5
        # Prefer mappings that avoid fragile default fields and expose richer metadata.
        if text_field and text_field != "text":
            score += 2.0
        if title_field:
            score += 0.5
        if isinstance(metadata_fields, dict):
            score += min(len(metadata_fields), 3) * 0.3
        score += min(len(name), 40) / 200.0
        return score

    def _external_signature(self, cfg: Any) -> str:
        """Create a canonical signature for equivalent external connections."""
        source_type = getattr(cfg, "source_type", "")
        source_type = source_type.value if hasattr(source_type, "value") else source_type
        return "|".join([
            self._normalize_signature_part(source_type),
            self._normalize_signature_part(getattr(cfg, "endpoint", "")),
            self._normalize_signature_part(getattr(cfg, "database", "")),
            self._normalize_signature_part(getattr(cfg, "table_or_query", "")),
            self._normalize_signature_part(getattr(cfg, "auth_method", "")),
        ])

    def _dedupe_external_sources(self, sources: list[Any], connected_only: bool = False) -> list[Any]:
        """Collapse duplicate source registrations that target the same underlying connection."""
        picked: dict[str, Any] = {}
        for cfg in sources:
            if connected_only and getattr(cfg, "status", "") != "connected":
                continue

            key = self._external_signature(cfg)
            current = picked.get(key)
            if current is None:
                picked[key] = cfg
                continue

            # Keep the better display candidate for runtime UX and filters.
            if self._source_quality_score(cfg) > self._source_quality_score(current):
                picked[key] = cfg

        return list(picked.values())

    def _safe_dict(self, value: Any) -> dict:
        return value if isinstance(value, dict) else {}

    def _normalize_doc(self, doc: dict, source_id: str, source_name: str, source_kind: str) -> dict:
        metadata = self._safe_dict(doc.get("metadata"))
        return {
            "id": str(doc.get("id") or doc.get("doc_id") or ""),
            "doc_id": str(doc.get("doc_id") or doc.get("id") or ""),
            "text": str(doc.get("text") or ""),
            "summary": str(doc.get("summary") or ""),
            "type": str(doc.get("type") or "unknown"),
            "source_file": str(
                doc.get("source_file") or doc.get("title") or source_name
            ),
            "source_id": source_id,
            "source_name": source_name,
            "source_kind": source_kind,
            "metadata": metadata,
            "score": float(doc.get("score") or 0.0),
        }

    def _match_filters(self, doc: dict, filters: Optional[dict]) -> bool:
        if not filters:
            return True
        metadata = self._safe_dict(doc.get("metadata"))
        text_blob = " ".join([
            str(doc.get("text") or ""),
            str(doc.get("summary") or ""),
        ]).strip().lower()
        for key, expected in filters.items():
            probe = ""
            if key in ("source", "source_name"):
                probe = str(doc.get("source_name") or "")
            elif key in ("type", "doc_type"):
                probe = str(doc.get("type") or "")
            elif key in ("entities", "topics", "key_phrases"):
                raw_val = metadata.get(key)
                expected_l = str(expected).strip().lower()

                if isinstance(raw_val, list):
                    if not any(str(v).strip().lower() == expected_l for v in raw_val):
                        if expected_l not in text_blob:
                            return False
                elif isinstance(raw_val, str) and raw_val.strip():
                    if expected_l not in raw_val.lower() and expected_l not in text_blob:
                        return False
                else:
                    if expected_l not in text_blob:
                        return False
                continue
            else:
                probe = str(metadata.get(key, ""))
            if probe.strip().lower() != str(expected).strip().lower():
                return False
        return True

    @staticmethod
    def _score_text(query: str, text: str) -> float:
        q_terms = [t for t in query.lower().split() if t]
        if not q_terms:
            return 0.0
        text_l = text.lower()
        matches = sum(1 for t in q_terms if t in text_l)
        return matches / max(len(q_terms), 1)

    def extraction_facets(
        self,
        source: Optional[str] = "all",
        filters: Optional[dict] = None,
        count: int = 120,
        top: int = 20,
    ) -> dict:
        """Compute lightweight extraction facets from runtime text.

        Used when persisted enrichment fields are unavailable for external sources.
        """
        docs = self.sample(source=source, count=max(20, count), filters=filters)
        if not docs:
            return {"entities": [], "topics": [], "key_phrases": []}

        stopwords = {
            "this", "that", "with", "from", "have", "has", "been", "were", "what", "when", "where", "which",
            "will", "would", "could", "should", "about", "into", "your", "their", "there", "these", "those",
            "customer", "agent", "service", "support", "call", "calls", "conversation", "document", "documents",
            "please", "also", "just", "very", "more", "most", "some", "many", "much", "make", "used", "using",
            "through", "within", "between", "across", "before", "after", "under", "over",
            "they", "them", "then", "than", "ours", "ourselves", "yourself", "yourselves",
        }
        entity_stop = {
            "The", "This", "That", "It", "If", "In", "At", "By", "On", "For",
            "Customer", "Agent", "Support", "Service", "Call", "Northwind Standard", "Northwind Health",
            "When", "Where", "Which", "What", "Who", "How", "Why", "You", "Your", "Yours",
            "They", "Them", "Their", "These", "Those", "Additionally", "Finally", "However", "Therefore",
            "Please", "Make", "Tips", "Note", "Also", "And", "But", "Or",
            "Develop", "Strong", "Excellent", "Proven", "Manage", "Monitor", "Ensure", "Knowledge",
            "Responsibilities", "Qualifications", "Bachelor", "Employees", "Services", "Summary", "Ability", "Oversee",
        }
        topic_blocklist = {
            "http", "https", "www", "com", "json", "source", "external", "uploaded", "records", "record",
            "assistant", "helpdesk", "contoso", "northwind", "standard", "health",
            "important", "includes", "cover", "covered", "contact", "other", "ensure", "understand",
            "provide", "services", "information", "necessary",
        }

        entity_counter: Counter[str] = Counter()
        topic_counter: Counter[str] = Counter()
        phrase_counter: Counter[str] = Counter()
        entity_lead_block = {"At", "In", "On", "For", "By", "With", "From", "The", "A", "An"}

        entity_re = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")
        token_re = re.compile(r"\b[a-zA-Z]{4,}\b")

        for doc in docs:
            text = str(doc.get("text") or "").strip()
            if not text:
                continue

            snippet = text[:2500]

            entities_seen: set[str] = set()
            for match in entity_re.findall(snippet):
                cleaned = " ".join(match.split()).strip()
                if not cleaned or cleaned in entity_stop:
                    continue
                if any(ch.isdigit() for ch in cleaned) or any(ch in cleaned for ch in ("/", "\\", "_", "@", ":", ".")):
                    continue
                parts = cleaned.split()
                if not parts or any(not p[:1].isupper() for p in parts):
                    continue
                if parts[0] in entity_lead_block:
                    continue
                # Single-word entities are usually generic tokens in this corpus.
                if len(parts) == 1:
                    continue
                entities_seen.add(cleaned)
            for ent in entities_seen:
                entity_counter[ent] += 1

            words = [w.lower() for w in token_re.findall(snippet)]
            words = [w for w in words if w not in stopwords and w not in topic_blocklist and len(w) >= 5]
            for token in set(words):
                topic_counter[token] += 1

            for idx in range(max(0, len(words) - 1)):
                a, b = words[idx], words[idx + 1]
                if a in stopwords or b in stopwords:
                    continue
                if a in topic_blocklist or b in topic_blocklist:
                    continue
                if a == b:
                    continue
                phrase_counter[f"{a} {b}"] += 1

        entities = [{"label": k, "value": int(v)} for k, v in entity_counter.most_common(top) if v >= 4]
        topics = [{"label": k, "value": int(v)} for k, v in topic_counter.most_common(top) if v >= 4]
        key_phrases = [{"label": k, "value": int(v)} for k, v in phrase_counter.most_common(top) if v >= 3]

        return {
            "entities": entities,
            "topics": topics,
            "key_phrases": key_phrases,
        }

    def list_sources(self) -> list[dict]:
        from src.api.modules.ingestion.service import ingestion_service
        from src.api.modules.data_sources.registry import data_source_registry

        ingestion_service._ensure_loaded()
        files = list(ingestion_service._uploaded_files.values())
        external = self._dedupe_external_sources(data_source_registry.list_all(), connected_only=False)

        uploaded_doc_count = sum(len(f.doc_ids or []) for f in files)
        sources: list[dict] = [
            {
                "id": "uploaded",
                "name": "Uploaded Documents",
                "kind": "uploaded",
                "connected": True,
                "count": uploaded_doc_count,
            }
        ]

        seed_count = len([f for f in files if (f.source or "uploaded") == "seed"])
        if seed_count > 0:
            sources.append(
                {
                    "id": "seed",
                    "name": "Built-in Scenario Data",
                    "kind": "seed",
                    "connected": True,
                    "count": seed_count,
                }
            )

        for src in external:
            sources.append(
                {
                    "id": src.id,
                    "name": src.name,
                    "kind": "external",
                    "source_type": src.source_type.value if hasattr(src.source_type, "value") else str(src.source_type),
                    "connected": src.status == "connected",
                    "count": int(src.doc_count or 0),
                    "health": src.status,
                }
            )

        return sources

    def resolve_external_source(self, source_ref: str) -> tuple[Optional[str], Optional[str]]:
        """Resolve any external source alias/id to the deduped canonical source."""
        from src.api.modules.data_sources.registry import data_source_registry

        ref = str(source_ref or "").strip().lower()
        if not ref:
            return None, None

        all_sources = data_source_registry.list_all()
        canonical = self._dedupe_external_sources(all_sources, connected_only=True)
        canonical_by_sig = {self._external_signature(cfg): cfg for cfg in canonical}

        # Direct canonical id/name match first.
        for cfg in canonical:
            if ref in (str(cfg.id).strip().lower(), str(cfg.name).strip().lower()):
                return str(cfg.id), str(cfg.name)

        # Alias/raw duplicate id/name maps to canonical by signature.
        for cfg in all_sources:
            if getattr(cfg, "status", "") != "connected":
                continue
            if ref not in (str(cfg.id).strip().lower(), str(cfg.name).strip().lower()):
                continue
            chosen = canonical_by_sig.get(self._external_signature(cfg))
            if chosen:
                return str(chosen.id), str(chosen.name)

        return None, None

    def sample(self, source: Optional[str], count: int = 20, filters: Optional[dict] = None) -> list[dict]:
        from src.api.modules.ingestion.service import ingestion_service
        from src.api.modules.data_sources.registry import data_source_registry

        ingestion_service._ensure_loaded()
        out: list[dict] = []

        include_uploaded = source in (None, "all", "uploaded", "seed")
        if include_uploaded:
            for doc in ingestion_service.documents.values():
                source_label = "seed" if getattr(doc.metadata, "source_type", "") == "seed" else "uploaded"
                if source in ("seed", "uploaded") and source_label != source:
                    continue
                norm = self._normalize_doc(
                    {
                        "id": doc.id,
                        "doc_id": doc.id,
                        "text": ingestion_service.normalize_text(doc),
                        "type": doc.type,
                        "source_file": doc.metadata.source_file or "uploaded",
                        "metadata": doc.metadata.model_dump() if hasattr(doc.metadata, "model_dump") else {},
                    },
                    source_id=source_label,
                    source_name="Built-in Scenario Data" if source_label == "seed" else "Uploaded Documents",
                    source_kind=source_label,
                )
                if self._match_filters(norm, filters):
                    out.append(norm)
                if len(out) >= count and source not in (None, "all"):
                    return out[:count]

        if source not in ("uploaded", "seed"):
            external_sources = self._dedupe_external_sources(data_source_registry.list_all(), connected_only=True)
            for cfg in external_sources:
                if source not in (None, "all") and cfg.id != source:
                    continue
                if cfg.status != "connected":
                    continue
                try:
                    rows = data_source_registry.sample(cfg.id, count=count)
                except Exception as ex:
                    logger.warning("Failed sampling source '%s': %s", cfg.name, ex)
                    continue
                for row in rows:
                    norm = self._normalize_doc(row, cfg.id, cfg.name, "external")
                    if self._match_filters(norm, filters):
                        out.append(norm)

        out.sort(key=lambda d: (d.get("score", 0.0), d.get("source_name", "")), reverse=True)
        return out[:count]

    def search(self, query: str, filters: Optional[dict] = None, source: Optional[str] = None, top_k: int = 5) -> list[dict]:
        from src.api.modules.ingestion.service import ingestion_service
        from src.api.modules.data_sources.registry import data_source_registry

        merged: list[dict] = []

        # Uploaded/seeded docs via in-memory normalized search.
        if source in (None, "all", "uploaded", "seed"):
            ingestion_service._ensure_loaded()
            for doc in ingestion_service.documents.values():
                source_kind = "seed" if getattr(doc.metadata, "source_type", "") == "seed" else "uploaded"
                if source in ("uploaded", "seed") and source_kind != source:
                    continue
                text = ingestion_service.normalize_text(doc)
                score = self._score_text(query, text)
                if score <= 0 and query.strip():
                    continue
                norm = self._normalize_doc(
                    {
                        "id": doc.id,
                        "doc_id": doc.id,
                        "text": text,
                        "summary": "",
                        "type": doc.type,
                        "source_file": doc.metadata.source_file or "uploaded",
                        "metadata": doc.metadata.model_dump() if hasattr(doc.metadata, "model_dump") else {},
                        "score": score if score > 0 else 0.01,
                    },
                    source_id=source_kind,
                    source_name="Built-in Scenario Data" if source_kind == "seed" else "Uploaded Documents",
                    source_kind=source_kind,
                )
                if self._match_filters(norm, filters):
                    merged.append(norm)

        # External live sources.
        if source not in ("uploaded", "seed"):
            for cfg in self._dedupe_external_sources(data_source_registry.list_live_sources(), connected_only=True):
                if source not in (None, "all") and cfg.id != source:
                    continue
                try:
                    docs = data_source_registry.search(cfg.id, query, top_k)
                except Exception as ex:
                    logger.warning("External search failed for '%s': %s", cfg.name, ex)
                    continue
                for d in docs:
                    norm = self._normalize_doc(d, cfg.id, cfg.name, "external")
                    if self._match_filters(norm, filters):
                        merged.append(norm)

        merged.sort(key=lambda d: d.get("score", 0.0), reverse=True)
        return merged[:top_k]

    def aggregate(self, request: dict) -> dict:
        source = request.get("source")
        field = str(request.get("field") or "type")
        top = int(request.get("top") or 10)
        filters = request.get("filters")

        # Push down aggregation when a single external source is selected.
        pushed = self._aggregate_external_pushdown(source=source, field=field, top=top)
        if pushed is not None:
            return pushed

        rows = self.sample(source=source, count=max(1000, top * 20), filters=filters)

        if not rows:
            return {"field": field, "total": 0, "items": []}

        counter: Counter = Counter()
        for row in rows:
            if field in ("source", "source_name"):
                value = row.get("source_name")
            elif field in ("type", "doc_type"):
                value = row.get("type")
            else:
                metadata = self._safe_dict(row.get("metadata"))
                value = metadata.get(field)
            label = str(value or "unknown").strip()
            if not label:
                continue
            counter[label] += 1

        return {
            "field": field,
            "total": len(rows),
            "items": [
                {"label": label, "value": int(count)}
                for label, count in counter.most_common(top)
            ],
        }

    def _aggregate_external_pushdown(self, source: Optional[str], field: str, top: int) -> Optional[dict]:
        """Run source-native aggregation for external systems when possible."""
        if source in (None, "all", "uploaded", "seed"):
            return None

        from src.api.modules.data_sources.registry import data_source_registry

        cfg = data_source_registry.get(source)
        if not cfg or cfg.status != "connected":
            return None

        source_type = cfg.source_type.value if hasattr(cfg.source_type, "value") else str(cfg.source_type)

        # Fabric SQL pushdown for source/type or mapped column aggregations.
        if source_type == "fabric":
            try:
                import pyodbc
                import struct
                from azure.identity import DefaultAzureCredential
                from src.api.modules.data_sources.base import validate_table_name

                table = validate_table_name(cfg.table_or_query)
                mapped_field = field
                if field in ("source", "source_name"):
                    return {
                        "field": field,
                        "total": int(cfg.doc_count or 0),
                        "items": [{"label": cfg.name, "value": int(cfg.doc_count or 0)}],
                    }
                if field in ("type", "doc_type"):
                    mapped_field = cfg.field_mapping.type_field or "type"
                elif cfg.field_mapping.metadata_fields and field in cfg.field_mapping.metadata_fields:
                    mapped_field = cfg.field_mapping.metadata_fields[field]

                if not mapped_field:
                    return None

                if cfg.connection_string:
                    conn = pyodbc.connect(cfg.connection_string, timeout=30)
                else:
                    credential = DefaultAzureCredential()
                    token = credential.get_token("https://database.windows.net/.default")
                    token_bytes = token.token.encode("utf-16-le")
                    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
                    conn_str = (
                        f"Driver={{ODBC Driver 18 for SQL Server}};"
                        f"Server={cfg.endpoint};"
                        f"Database={cfg.database};"
                        f"Encrypt=yes;TrustServerCertificate=no;"
                    )
                    conn = pyodbc.connect(conn_str, attrs_before={1256: token_struct})

                cursor = conn.cursor()
                sql = (
                    f"SELECT TOP {top} CAST([{mapped_field}] AS NVARCHAR(256)) AS label, COUNT(*) AS value "
                    f"FROM [{table}] "
                    f"GROUP BY [{mapped_field}] "
                    f"ORDER BY value DESC"
                )
                cursor.execute(sql)
                rows = cursor.fetchall()
                conn.close()

                items = [{"label": str(r[0] or "unknown"), "value": int(r[1] or 0)} for r in rows]
                return {
                    "field": field,
                    "total": int(cfg.doc_count or sum(i["value"] for i in items)),
                    "items": items,
                }
            except Exception as ex:
                logger.warning("Fabric aggregate pushdown failed for '%s': %s", cfg.name, ex)
                return None

        # Azure AI Search pushdown via facets where available.
        if source_type == "azure_search":
            try:
                from azure.identity import DefaultAzureCredential
                from azure.search.documents import SearchClient

                facet_field = None
                if field in ("source", "source_name"):
                    return {
                        "field": field,
                        "total": int(cfg.doc_count or 0),
                        "items": [{"label": cfg.name, "value": int(cfg.doc_count or 0)}],
                    }
                if field in ("type", "doc_type"):
                    facet_field = cfg.field_mapping.type_field or "type"
                elif cfg.field_mapping.metadata_fields and field in cfg.field_mapping.metadata_fields:
                    facet_field = cfg.field_mapping.metadata_fields[field]
                else:
                    facet_field = field

                if not facet_field:
                    return None

                client = SearchClient(
                    endpoint=cfg.endpoint,
                    index_name=cfg.table_or_query,
                    credential=DefaultAzureCredential(),
                )
                results = client.search(
                    search_text="*",
                    top=0,
                    facets=[f"{facet_field},count:{top}"],
                )
                facets = getattr(results, "get_facets", lambda: {})() or {}
                values = facets.get(facet_field, []) if isinstance(facets, dict) else []
                items = [
                    {"label": str(v.get("value") or "unknown"), "value": int(v.get("count") or 0)}
                    for v in values if isinstance(v, dict)
                ]
                return {
                    "field": field,
                    "total": int(cfg.doc_count or sum(i["value"] for i in items)),
                    "items": items[:top],
                }
            except Exception as ex:
                logger.warning("Azure Search aggregate pushdown failed for '%s': %s", cfg.name, ex)
                return None

        return None

    def schema(self, source: Optional[str] = None) -> dict:
        from src.api.modules.data_sources.registry import data_source_registry

        fields = {"id", "doc_id", "text", "summary", "type", "source_file", "source_name", "source_kind"}
        if source not in (None, "all", "uploaded", "seed"):
            cfg = data_source_registry.get(source)
            if not cfg:
                return {"source": source, "fields": []}
            try:
                columns = data_source_registry.get_schema(source)
                fields.update(c.name for c in columns)
            except Exception:
                pass
        else:
            for cfg in self._dedupe_external_sources(data_source_registry.list_all(), connected_only=False):
                try:
                    columns = data_source_registry.get_schema(cfg.id)
                    fields.update(c.name for c in columns)
                except Exception:
                    continue

        return {"source": source or "all", "fields": sorted(fields)}

    def count(self, source: Optional[str] = None, filters: Optional[dict] = None) -> int:
        if filters:
            # Filtered exact counts vary by source; use sampled fallback for now.
            sample_size = 5000
            rows = self.sample(source=source, count=sample_size, filters=filters)
            return len(rows)

        from src.api.modules.ingestion.service import ingestion_service
        from src.api.modules.data_sources.registry import data_source_registry

        ingestion_service._ensure_loaded()

        uploaded_count = 0
        seed_count = 0
        for doc in ingestion_service.documents.values():
            if getattr(doc.metadata, "source_type", "") == "seed":
                seed_count += 1
            else:
                uploaded_count += 1

        if source == "uploaded":
            return uploaded_count
        if source == "seed":
            return seed_count

        if source not in (None, "all"):
            cfg = data_source_registry.get(source)
            return int(cfg.doc_count or 0) if cfg else 0

        external_total = sum(
            int(cfg.doc_count or 0)
            for cfg in self._dedupe_external_sources(data_source_registry.list_all(), connected_only=True)
            if cfg.status == "connected"
        )
        return uploaded_count + seed_count + external_total

    def health(self, source: Optional[str] = None) -> dict:
        from src.api.modules.data_sources.registry import data_source_registry

        if source in (None, "all", "uploaded", "seed"):
            statuses = [{"source": s["id"], "status": "connected" if s.get("connected") else "error"} for s in self.list_sources()]
            return {"status": "ok", "sources": statuses}

        cfg = data_source_registry.get(source)
        if not cfg:
            return {"status": "missing", "source": source}

        return {
            "status": "ok" if cfg.status == "connected" else "error",
            "source": cfg.id,
            "name": cfg.name,
            "message": cfg.error_message or cfg.status,
        }


runtime_registry = UnifiedDataSourceRegistry()
