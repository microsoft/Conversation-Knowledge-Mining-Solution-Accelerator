# Knowledge Mining Solution Accelerator — Status Update

**Date:** May 8, 2026  
**Audience:** Engineering team & managers

---

## Executive Summary

**What it is.** A modular and generic solution accelerator for knowledge mining. Users upload documents (PDF, DOCX, images, JSON, CSV, TXT) or connect to external data sources (Microsoft Fabric, SQL databases, Azure Synapse, ODBC, or an existing Azure AI Search index). The platform extracts knowledge using AI and lets users explore results through natural language chat and auto-generated dashboards. Deploy with one command (`azd up`), bring your data, start asking questions.

**Why we built it.** Organizations sit on large volumes of unstructured data but lack tools to interact with it conversationally. Existing approaches require manual exploration, custom pipelines per dataset, and hardcoded dashboards. This accelerator gives you a working end-to-end system out of the box — upload any data, and the platform adapts its insights, filters, and chat grounding to your content automatically.

**Where we are today.** The core platform is functional end-to-end. Document ingestion (multi-format, async two-stage queue), hybrid search (keyword + vector), RAG chat with GPT-4o, LLM-planned insights dashboard, configurable pipelines, and 5 external data source connectors are all built and working. Frontend has Home, Insights, Explore, Data Sources, Data Explorer, and Pipelines pages. Infrastructure deploys cleanly via `azd up` with Managed Identity and RBAC.

**What still needs work.** Testing (no real test suite yet), production hardening (retry logic, rate limiting, monitoring), CI/CD, and some frontend navigation polish. Details in the [What's left](#whats-left-to-do) section.

---

## What's been done

### Infrastructure
- Full Bicep IaC with `azd up` deployment (12 modules)
- Managed Identity + RBAC everywhere — no API keys in app config
- Docker support (`docker-compose.yaml`) for local dev
- Deployment scripts: agent setup, sample data seeding, teardown

### Backend (FastAPI / Python)
- **Document ingestion** — two-stage async queue pipeline (upload → extract → chunk → embed → index). Upload returns instantly; processing runs in background
- **Hybrid search** — keyword (BM25) + vector (HNSW) in Azure AI Search
- **RAG chat** — GPT-4o answers grounded in your documents, with citations
- **Insights engine** — LLM analyzes your data schema, plans which charts matter, SQL computes exact numbers. Adapts to any dataset
- **Pipeline engine** — YAML-defined processing pipelines with 11 pluggable capabilities (classify, summarize, extract entities, etc.)
- **External data connectors** — 5 adapters (Fabric, SQL, Synapse, ODBC, Azure AI Search). Auto-detects field mapping. Supports ingest, live query, or both
- **Auth** — EasyAuth (Azure AD) with role-based access control

### Frontend (React / Fluent UI 2)
- **Home** — drag-and-drop upload, data status, processing progress
- **Explore** — chat with your data, filter panel, chat sessions, source citations
- **Insights** — auto-generated dashboard (KPIs, donut/bar/line/word cloud charts, filterable)
- **Data Sources** — manage connected sources and uploaded files
- **Data Explorer** — browse documents, extract entities, summarize on demand
- **Pipelines** — view and run processing pipelines

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
| Structured data | **Azure SQL Database** | Metadata, enrichment cache, data source configs |
| Chat history | **Azure Cosmos DB** | Low-latency session storage |
| File + queue storage | **Azure Blob + Queue** | Raw file storage + async job queue for the processing pipeline |
| IaC | **Bicep + azd** | Native Azure, modular, one-command deploy |
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

## What's left to do

| # | Item | Details |
|---|------|---------|
| 1 | **Nav links for Data Sources + Pipelines** | Pages exist and work, but the nav links are commented out / missing in `Layout.tsx`. Quick fix. |
| 2 | **Quick-connect wizard UI** | Backend `/quick-connect` endpoint is built. Need a multi-step frontend dialog for the "bring your data" flow (pick type → connect → test → map fields → done). |
| 3 | **Testing** | No real test suite yet. Need unit tests per module, integration tests for the ingestion pipeline, E2E tests for the chat flow. |
| 4 | **Production hardening** | Rate limiting, retry policies for the queue worker, connection pooling for SQL/ODBC adapters, dead-letter handling, graceful shutdown. |
| 5 | **Monitoring** | App Insights integration, structured logging, request tracing, pipeline metrics. |
| 6 | **CI/CD** | GitHub Actions for lint, test, build, and `azd` deploy on merge. |
| 7 | **Docs** | API reference is auto-generated (OpenAPI), but we need a user guide and a developer guide (how to add connectors, capabilities, pipeline steps). |
| 8 | **Auth polish** | Frontend login/logout flow, protected routes, session timeout, role-based UI visibility. |

---

## Challenges & risks

| Challenge | Impact | Mitigation |
|-----------|--------|------------|
| **Queue worker reliability** | If the worker crashes mid-processing, documents get stuck in "processing" state forever | Need retry logic, dead-letter queue, and a status recovery mechanism |
| **No tests** | Can't confidently refactor or add features without breaking things | Prioritize test coverage for ingestion pipeline and RAG flow first |
| **ODBC driver availability** | Fabric, Synapse, and SQL adapters require ODBC Driver 18 installed on the host | Docker image includes it; App Service may need a custom startup script |
| **Embedding costs at scale** | ada-002 calls on large datasets get expensive fast | Embedding cache exists, but no cost monitoring or throttling yet |
| **Data Sources nav hidden** | Users can't discover the feature | Literally one line to uncomment — just needs the polish pass |
| **Region availability** | Not all Azure services are available in all regions (especially Content Understanding + AI Foundry) | README documents prerequisites; `azd` will fail fast with clear errors |
| **Local dev without Azure** | Queue worker falls back to in-process tasks, but Content Understanding and AI Search require live Azure resources | Sample data path (`load-default`) works without CU, but chat needs Search + OpenAI |

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
