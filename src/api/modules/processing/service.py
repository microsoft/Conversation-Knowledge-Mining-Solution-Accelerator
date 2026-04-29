from typing import Optional

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from src.api.config import get_settings
from src.api.modules.ingestion.service import ingestion_service
from src.api.modules.processing.models import (
    SummarizeResponse,
    Entity,
    EntityExtractionResponse,
    BatchProcessResult,
)


class ProcessingService:
    """Reusable AI processing: summarization, entity extraction."""

    def __init__(self):
        self._client: Optional[AzureOpenAI] = None

    def _get_client(self) -> AzureOpenAI:
        if self._client is None:
            settings = get_settings()
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
            self._client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version="2024-10-21",
            )
        return self._client

    def summarize(self, text: str, max_length: int = 200, style: str = "concise") -> SummarizeResponse:
        style_prompts = {
            "concise": f"Summarize the following text in {max_length} words or fewer. Be direct and concise.",
            "detailed": f"Provide a detailed summary of the following text in about {max_length} words. Include key details.",
            "bullet_points": f"Summarize the following text as bullet points. Use at most {max_length} words total.",
        }
        prompt = style_prompts.get(style, style_prompts["concise"])

        settings = get_settings()
        client = self._get_client()
        response = client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            max_tokens=max_length * 2,
        )

        return SummarizeResponse(
            original_length=len(text.split()),
            summary=response.choices[0].message.content,
            style=style,
        )

    def extract_entities(
        self, text: str, entity_types: Optional[list[str]] = None
    ) -> EntityExtractionResponse:
        type_instruction = ""
        if entity_types:
            type_instruction = f"Only extract these entity types: {', '.join(entity_types)}."
        else:
            type_instruction = (
                "Extract all relevant entities including: Person, Organization, Product, "
                "Location, Date, Issue, Resolution, Policy, Amount, Reference Number."
            )

        settings = get_settings()
        client = self._get_client()
        response = client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are an entity extraction system. {type_instruction}\n"
                        "Return a JSON array of objects with 'text', 'type', and 'confidence' (0-1) fields.\n"
                        "Return ONLY the JSON array, no other text."
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            max_tokens=1500,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            raw = raw.rsplit("```", 1)[0]

        import json
        try:
            entities_data = json.loads(raw)
        except json.JSONDecodeError:
            entities_data = []

        entities = [
            Entity(
                text=e.get("text", ""),
                type=e.get("type", "Unknown"),
                confidence=e.get("confidence"),
            )
            for e in entities_data
            if isinstance(e, dict) and e.get("text")
        ]

        return EntityExtractionResponse(entities=entities, entity_count=len(entities))

    def batch_process(
        self,
        doc_ids: Optional[list[str]] = None,
        operations: Optional[list[str]] = None,
    ) -> BatchProcessResult:
        """Run operations (summarize, extract_entities) on ingested documents."""
        ops = operations or ["summarize"]
        errors: list[str] = []
        results: dict[str, dict] = {}

        docs = ingestion_service.documents
        if doc_ids:
            docs = {k: v for k, v in docs.items() if k in doc_ids}

        for doc_id, doc in docs.items():
            text = ingestion_service.normalize_text(doc)
            if not text.strip():
                continue

            doc_result: dict = {}
            try:
                if "summarize" in ops:
                    s = self.summarize(text)
                    doc_result["summary"] = s.summary

                if "extract_entities" in ops:
                    e = self.extract_entities(text)
                    doc_result["entities"] = [ent.model_dump() for ent in e.entities]

                results[doc_id] = doc_result
            except Exception as ex:
                errors.append(f"{doc_id}: {str(ex)}")

        return BatchProcessResult(processed=len(results), results=results, errors=errors)

    def generate_insights(self, file_ids: list[str] | None = None) -> dict:
        """Generate rich, generic, LLM-driven insights from the dataset.
        
        Args:
            file_ids: Optional list of file IDs to scope insights to.
                      If None, analyzes all documents.
        """
        import json
        settings = get_settings()

        stats = ingestion_service.get_stats()
        all_files = ingestion_service.uploaded_files
        filter_schema = ingestion_service.filter_schema

        # Scope to specific files if requested
        if file_ids:
            files = [f for f in all_files if f.id in file_ids]
            # Recalculate record count for scoped files
            total_records = sum(f.doc_count for f in files)
        else:
            files = all_files
            total_records = stats.total_documents

        file_count = len(files)

        if file_count == 0:
            return {"headline": "No Documents to Analyze", "narrative": "Upload documents to generate insights."}

        # When scoped to specific files, build dimensions only from those files
        dimensions: dict = {}
        if file_ids:
            # Build dimensions from scoped files' filter_values + keywords
            dim_counts: dict[str, dict[str, int]] = {}
            for f in files:
                for dim_id, vals in f.filter_values.items():
                    if dim_id not in dim_counts:
                        dim_counts[dim_id] = {}
                    for v in vals:
                        dim_counts[dim_id][v] = dim_counts[dim_id].get(v, 0) + 1
                for kw in f.keywords:
                    dim_counts.setdefault("keywords", {})[kw] = dim_counts.get("keywords", {}).get(kw, 0) + 1
            dimensions = dim_counts
        else:
            for dim in filter_schema.dimensions:
                dim_counts_schema = {v.label: v.count for v in dim.values}
                dimensions[dim.label] = dim_counts_schema
            if not dimensions:
                # Fallback: use document type counts
                if stats.by_type:
                    dimensions["Document Type"] = stats.by_type

        file_summaries = [{"filename": f.filename, "summary": f.summary, "keywords": f.keywords,
                           "record_count": f.doc_count} for f in files if f.summary]

        scope_label = f"Analyzing ONLY these {file_count} file(s): {', '.join(f.filename for f in files)}" if file_ids else "Analyzing all documents"

        prompt = f"""You are a senior data intelligence analyst. Your job is to tell the STORY hidden in this data — not just report numbers.

SCOPE: {scope_label}
DATA:
- Files: {file_count} | Records: {total_records}
- Dimensions: {json.dumps(dimensions, indent=2)}
- File summaries: {json.dumps(file_summaries, indent=2)}

Generate a JSON intelligence report with these sections:

1. "headline": A single bold headline (6-10 words) that captures the most important finding. Like a newspaper headline. Example: "Outdated Hardware Drives 50% of All Failures"

2. "narrative": ONE sentence (max 25 words) that gives context to the headline. Not a summary — just the "so what" in one line.

3. "confidence": "High|Medium|Low"

4. "signals": Array of exactly 3 items. Each represents a different type of intelligence:
   {{
     "category": "pattern|risk|opportunity",
     "label": "short title (3-5 words)",
     "metric": "key number or %",
     "interpretation": "1 sentence: what this means and why it matters",
     "action": "1 sentence: what to do about it"
   }}

5. "deep_findings": Array of 4-6 items. Each is a DEEP finding (not surface-level):
   {{
     "finding": "specific observation with evidence",
     "why_it_matters": "business/operational implication",
     "recommendation": "concrete action to take"
   }}

6. "causal_chains": Array of 2-3 root cause chains:
   {{
     "chain": "CauseA → EffectB → OutcomeC",
     "explanation": "why this chain exists"
   }}

7. "entity_map": Array of top 4-6 entities with context:
   {{
     "name": "entity name",
     "relevance": 0-100 (how central to the dataset),
     "role": "what role this entity plays in the data",
     "connections": ["related entity 1", "related entity 2"]
   }}

8. "risks": Array of 2-4 risks:
   {{
     "risk": "what could go wrong",
     "severity": "high|medium|low",
     "evidence": "what in the data supports this",
     "mitigation": "how to address it"
   }}

9. "opportunities": Array of 2-3 opportunities:
   {{
     "opportunity": "what could be improved",
     "potential_impact": "expected outcome",
     "next_step": "first action to take"
   }}

10. "questions_to_investigate": Array of 3-4 questions that would deepen understanding. These should be NON-OBVIOUS questions that a smart analyst would ask next.

CRITICAL RULES:
- NEVER just restate numbers. INTERPRET them.
- Every finding must answer "so what?"
- Be domain-agnostic — work for ANY dataset
- Write like a consultant, not a database query
- Connect findings to each other — show the story
- Focus on WHAT TO DO, not just what happened
Output strictly valid JSON."""

        client = self._get_client()
        response = client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=[
                {"role": "system", "content": "You are a senior intelligence analyst. You find the story in data and tell it clearly. Every insight must be actionable. Never just restate statistics — always interpret and recommend. Base ALL analysis ONLY on the provided data. Do NOT use prior knowledge, external information, or make assumptions beyond what is explicitly present in the data. If the data is insufficient for a section, state that clearly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            return {"summary": "Unable to generate insights.", "stats": [], "top_dimensions": [], "key_findings": [], "entity_types": []}

    def generate_insights_from_external(self, external_index_id: str) -> dict:
        """Generate insights by sampling documents from an external Azure AI Search index."""
        import json

        from src.api.modules.ingestion.external_index import external_index_service
        index = external_index_service.get(external_index_id)
        if not index:
            return {"headline": "Index Not Found", "narrative": "Could not connect to the specified index."}

        # Sample documents
        samples = external_index_service.sample_documents(external_index_id, sample_size=25)
        if not samples:
            return {"headline": "No Documents Found", "narrative": "The connected index appears to be empty."}

        settings = get_settings()
        doc_snippets = []
        for s in samples:
            text = s.get("text", "")[:300]
            title = s.get("title", s.get("id", ""))
            doc_snippets.append({"id": s["id"], "title": title, "text": text})

        prompt = f"""You are a senior data intelligence analyst. Analyze these {len(doc_snippets)} documents from an external knowledge base.

INDEX: {index.name} ({index.doc_count} total documents, showing {len(doc_snippets)} samples)

Documents:
{json.dumps(doc_snippets, indent=2)}

Generate the same JSON intelligence report format:
1. "headline": Bold headline (6-10 words)
2. "narrative": ONE sentence summary
3. "confidence": "High|Medium|Low"
4. "signals": Array of 3 metrics (category: pattern|risk|opportunity, label, metric, interpretation)
5. "deep_findings": Array of 4-6 findings (finding, why_it_matters, recommendation)
6. "causal_chains": Array of 2-3 root cause chains (chain, explanation)
7. "entity_map": Array of top entities (name, relevance 0-100, role, connections[])
8. "risks": Array of risks (risk, severity high|medium|low, evidence, mitigation)
9. "opportunities": Array of opportunities (opportunity, potential_impact, next_step)
10. "questions_to_investigate": Array of 3-4 follow-up questions

CRITICAL: Be domain-agnostic. Output strictly valid JSON."""

        client = self._get_client()
        response = client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=[
                {"role": "system", "content": "You are a senior intelligence analyst. Every insight must be actionable. Base ALL analysis ONLY on the provided documents. Do NOT use prior knowledge, external information, or make assumptions beyond what is explicitly present in the documents. If the data is insufficient for a section, state that clearly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            return {"headline": "Analysis Failed", "narrative": "Could not parse insights."}

    def generate_insights_from_data_source(self, data_source_id: str) -> dict:
        """Generate insights by sampling documents from a connected data source."""
        import json

        from src.api.modules.data_sources.registry import data_source_registry
        config = data_source_registry.get(data_source_id)
        if not config:
            return {"headline": "Source Not Found", "narrative": "Could not find the specified data source."}

        samples = data_source_registry.sample(data_source_id, count=25)
        if not samples:
            return {"headline": "No Data Found", "narrative": "The connected source appears to be empty."}

        settings = get_settings()
        doc_snippets = []
        for s in samples:
            text = str(s.get("text", ""))[:300]
            title = s.get("title", s.get("id", ""))
            doc_snippets.append({"id": s.get("id", ""), "title": title, "text": text})

        prompt = f"""You are a senior data intelligence analyst. Analyze these {len(doc_snippets)} records from an external data source.

SOURCE: {config.name} ({config.source_type.value}, {config.doc_count} total rows, showing {len(doc_snippets)} samples)

Documents:
{json.dumps(doc_snippets, indent=2)}

Generate the same JSON intelligence report format:
1. "headline": Bold headline (6-10 words)
2. "narrative": ONE sentence summary
3. "confidence": "High|Medium|Low"
4. "signals": Array of 3 metrics (category: pattern|risk|opportunity, label, metric, interpretation)
5. "deep_findings": Array of 4-6 findings (finding, why_it_matters, recommendation)
6. "causal_chains": Array of 2-3 root cause chains (chain, explanation)
7. "entity_map": Array of top entities (name, relevance 0-100, role, connections[])
8. "risks": Array of risks (risk, severity high|medium|low, evidence, mitigation)
9. "opportunities": Array of opportunities (opportunity, potential_impact, next_step)
10. "questions_to_investigate": Array of 3-4 follow-up questions

CRITICAL: Be domain-agnostic. Output strictly valid JSON."""

        client = self._get_client()
        response = client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=[
                {"role": "system", "content": "You are a senior intelligence analyst. Every insight must be actionable. Base ALL analysis ONLY on the provided documents. Do NOT use prior knowledge, external information, or make assumptions beyond what is explicitly present in the documents. If the data is insufficient for a section, state that clearly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            return {"headline": "Analysis Failed", "narrative": "Could not parse insights."}


processing_service = ProcessingService()
