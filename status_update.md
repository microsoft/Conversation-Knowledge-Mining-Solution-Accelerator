# Knowledge Mining Solution Accelerator — Status Update

---

## Summary

**What it is.** A modular and generic solution accelerator for knowledge mining. Users upload documents (PDF, DOCX, images, JSON, CSV, TXT) or connect to external data sources (Microsoft Fabric, SQL databases, Azure Synapse, ODBC, or an existing Azure AI Search index). The platform extracts knowledge using AI and lets users explore results through natural language chat and auto-generated dashboards. Deploy with one command (`azd up`), bring your data, start asking questions.

**Why we built it.** Every team has data they wish they could just talk to — call transcripts, contracts, research papers, support tickets, patient records, policy documents. But building a knowledge mining solution from scratch for each use case takes months. This accelerator eliminates that. Deploy once, bring whatever data you have, and the platform adapts. The dashboards, filters, chat behavior, and processing pipelines all shape themselves to your content. No domain-specific code, no hardcoded schemas.

**Where we are today.** The core platform is functional end-to-end. Document ingestion (multi-format, async two-stage queue), hybrid search (keyword + vector), RAG chat with GPT-4o, LLM-planned insights dashboard, configurable pipelines, and 5 external data source connectors are all built and working. Frontend has Home, Insights, Explore — all restructured with dedicated CSS module files and cleaned-up component layouts. The Explore page now shows source citations inline under each answer with clean filenames and snippets (no more raw UUIDs or redundant side panel). Infra deploys cleanly via `azd up` with Managed Identity and RBAC. Queue Storage RBAC roles are provisioned. A two-stage async pipeline (extract → chunk/embed/index) runs via Azure Queue Storage.

**What still needs work.** Testing, quick-connect wizard UI (backend endpoint is built), use-case selection flow, docs.
---

## What's been done

### Infrastructure
- Full Bicep with `azd up` deployment (still has to test end-to-end)
- Managed Identity + RBAC everywhere — no API keys in app config
- Queue Storage RBAC roles added for the two-stage processing pipeline
- Docker support (`docker-compose.yaml`) for local dev
- Deployment scripts: agent setup, sample data seeding, teardown
- ACR-based container deployment in infra

### Backend (FastAPI / Python)
- **Document ingestion** — Users upload files, the system processes them in the background via a two-stage async queue pipeline (extract → chunk/embed/index) through Azure Queue Storage. The upload response is instant. File status tracking fixed so earlier stages no longer overwrite later status
- **External data connectors** — Connect to Fabric, SQL databases, Synapse, ODBC sources, or an existing Azure AI Search index. The system figures out which columns map to which fields. Can pull data in, query live, or both
- **Hybrid search** — Combines keyword matching and semantic similarity for better results
- **RAG chat** — Users ask questions in natural language, the system finds relevant content and GPT-4o generates an answer with citations
- **Insights engine** — Looks at what data you have, decides which charts and KPIs are useful, and builds a dashboard automatically. No hardcoded charts — adapts to any dataset
- **Auth** — Azure AD login via App Service EasyAuth, with role-based access control

### Frontend (React / Fluent UI)
- **Home** — Landing page where users drag-and-drop files or see the status of their data. Shows which files are still processing and which are ready to explore. Restructured with dedicated `Home.module.css`
- **Explore** — The main chat experience. Users type questions in plain English, get answers grounded in their data with source citations shown inline under each answer. Source labels now show clean filenames instead of raw UUIDs, with truncated snippets. The redundant right-side sources panel has been removed. Chat history sidebar for saving/loading past sessions. Restructured with dedicated `Explore.module.css`
- **Insights** — A dashboard that builds itself based on your data. Users see KPIs, charts (donut, bar, line, word cloud), and key findings without configuring anything. They can filter and drill down. Restructured with updated `Insights.module.css`
- **Data Explorer** — A browsing view for individual documents. Users can search, open a document, ask for a summary, or extract entities (people, places, topics) on the fly
- **Pipelines** — Shows available processing workflows and lets users run them manually. Each pipeline displays its steps and current status

---

## Tech stack & why

| Component | Product | Why |
|-----------|---------|-----|
| Backend API | **FastAPI** | Async-native, auto-generated OpenAPI docs, dependency injection |
| Frontend | **React + Fluent UI 2** | Microsoft design system, accessible components, TypeScript |
| LLM (chat + insights) | **Azure OpenAI GPT-4o** | Best available model for grounded Q&A and reasoning |
| Embeddings | **text-embedding-ada-002** | Proven embedding model, 1536 dims, good cost/quality ratio |
| Vector + keyword search | **Azure AI Search** | Hybrid search (BM25 + HNSW) in one service, managed |
| Document extraction | **Azure Content Understanding** | Handles PDF, images, handwriting, tables — multi-modal |
| Agent orchestration | **Azure AI Foundry** | Managed agent service with tool support |
| LLM client layer | **Foundry IQ (`azure-ai-projects`)** | All model access (chat, embeddings) goes through a single Foundry Project. Centralizes governance, tracing, and quotas. Falls back to direct Azure OpenAI SDK when not configured. |
| Structured data | **Azure SQL Database** | Metadata, enrichment cache, data source configs |
| Chat history | **Azure Cosmos DB** | Low-latency session storage |
| File + queue storage | **Azure Blob + Queue** | Raw file storage + async job queue for the processing pipeline |
| Auth | **App Service EasyAuth** | Zero-code Azure AD integration |

---

## Architecture

```
┌──────────┐         ┌──────────────────┐         ┌───────────────────┐
│  Browser │  HTTP   │  Frontend        │  REST   │  Backend          │
│          │────────▶│  React / Fluent  │────────▶│  FastAPI / Python │
└──────────┘         └──────────────────┘         └─────────┬─────────┘
                                                            │
                     ┌──────────────────────────────────────┼──────────────────┐
                     │                                      │                  │
                     ▼                                      ▼                  ▼
            ┌─────────────────┐                    ┌─────────────┐   ┌─────────────────┐
            │  Azure OpenAI   │                    │  Azure AI   │   │  Azure Content   │
            │  GPT-4o + ada-2 │                    │  Search     │   │  Understanding   │
            └─────────────────┘                    │  (HNSW)     │   └────────┬────────┘
                     │                             └──────┬──────┘            │
                     ▼                                    ▼                   ▼
            ┌─────────────────┐                    ┌─────────────┐   ┌─────────────────┐
            │  AI Foundry     │                    │  Azure SQL  │   │  Blob + Queue   │
            │  Agent Service  │                    │  Database   │   │  Storage        │
            └─────────────────┘                    └─────────────┘   └─────────────────┘
                                                   ┌─────────────┐
                                                   │  Cosmos DB  │
                                                   └─────────────┘
```

**Document processing flow:**
```
Upload (instant response)
  → Blob Storage (raw file)
  → Queue: extraction
       → Content Understanding (text, summary, topics, key phrases)
       → Queue: enrichment
            → Chunk text (1000 chars, 200 overlap, paragraph-aware)
            → Embed (ada-002, 1536 dims, cached)
            → Index in AI Search (HNSW, upserts, content-hash IDs)
            → Status → "ready"
```

---


---
## How it's modular & use-case agnostic

The platform is designed so you can swap data, change the domain, or extend behavior without modifying core code.

**One platform, any use case.** There is zero domain-specific logic in the codebase. The same deployment that analyzes call center transcripts can analyze legal contracts, HR policies, insurance claims, academic research, engineering specs, or customer feedback — just swap the data. The system adapts automatically:

| What adapts | How |
|-------------|-----|
| **Dashboard charts & KPIs** | The insights engine reads your data's schema and values, then uses GPT-4o to decide which visualizations make sense. Feed it support tickets and you get sentiment breakdowns; feed it contracts and you get clause categories. |
| **Search filters** | Filters are generated from your data's actual fields and values — not predefined. Different datasets produce different filter panels. |
| **Chat grounding** | RAG retrieval works on whatever content is indexed. The system prompt is configurable via `prompts.yaml` — change it per use case without touching code. |
| **Field mapping** | When connecting a data source, the system auto-detects which columns are the ID, text body, title, timestamp, etc. Works across schemas without manual config for most datasets. |

**Where use-case selection is headed:**

The goal is to let deployers pick a use case during or right after deployment — not buried in code. This isn't fully built yet, but the plan:

- **During deployment (`azd up`)** — A parameter or prompt that selects a use-case pack (e.g., "call center", "legal review", "general"). This would set the system prompt, seed sample data, configure default pipelines, and apply the right field mappings automatically.
- **Post-deployment script** — A script like `./scripts/setup-usecase.ps1 --usecase telecom` that applies the use-case configuration to an already-deployed instance. Swap the use case without redeploying infrastructure.

**Use cases it supports :**

| Use case | Data type | What users get |
|----------|-----------|----------------|
| **Call center analytics** | JSON call transcripts | Sentiment trends, topic clusters, agent performance, Q&A over conversations |
| **Telecom support** | Call transcripts + WAV files | Same as above, with audio file ingestion |
| **Legal / compliance review** | Contracts, policies (PDF/DOCX) | Clause extraction, risk classification, searchable knowledge base |
| **Healthcare** | Clinical notes, reports | Entity extraction (conditions, medications), summarization, chat Q&A |
| **HR / internal knowledge** | Policy docs, handbooks, FAQs | Employees ask questions and get answers grounded in company docs |
| **Research & academia** | Papers, articles, datasets | Topic clustering, literature Q&A, cross-document insights |
| **Customer feedback** | Surveys, reviews, support tickets | Sentiment analysis, issue categorization, trend dashboards |
| **Insurance claims** | Claim forms, adjuster notes | Entity extraction, status tracking, pattern detection |
| **Any existing search index** | Azure AI Search index | Instant chat over pre-indexed data — zero upload, zero processing |

The point: **you don't pick a use case when you build the accelerator — you pick it when you bring your data.** The platform is the same every time.


---

## To do

| # | Item | Status | Details |
|---|------|--------|---------|
| 1 | **Copilot Studio agent** | Not started | Build a Copilot Studio agent that connects to the KM backend APIs. Users would interact with their knowledge base directly from Teams, M365, or any Copilot Studio channel — without needing to open the web app. The agent calls the RAG (`/api/rag`) and Insights (`/api/insights`) endpoints, so the same grounded answers and dashboard data are available conversationally inside the tools people already use. |
| 2 | **Quick-connect wizard UI** | Backend done | Backend `/quick-connect` endpoint is built and working. Need a multi-step frontend dialog for the "bring your data" flow. |
| 3 | **Use-case selection flow** | Not started | Let deployers pick a scenario during `azd up` or via a post-deploy script that auto-configures prompts, sample data, pipelines, and field mappings. `setup-data.ps1` script added as a starting point. |
| 4 | **Testing** | Not started | Unit tests per module, integration tests for the ingestion pipeline, E2E tests for the chat flow. |
| 5 | **Docs** | Not started | User guide and developer guide (how to add connectors, capabilities, pipeline steps). |

---

## How to run it

```bash
# Deploy to Azure
azd auth login
azd up

# Post-deploy
./infra/scripts/setup-agent.ps1       # Create AI agent
./scripts/seed-sample-data.ps1        # Load sample data (optional)

# Local dev
python -m venv venv && venv\Scripts\activate
pip install -r src/api/requirements.txt
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

cd src/app && npm install && npm start

# Tear down
azd down
```
