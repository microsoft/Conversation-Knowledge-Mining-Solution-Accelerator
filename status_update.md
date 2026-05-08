# Knowledge Mining Solution Accelerator — Status Update

**Date:** May 8, 2026  
**Audience:** Engineering team & managers

---

## Executive Summary

**What it is.** A modular and generic solution accelerator for knowledge mining. Users upload documents (PDF, DOCX, images, JSON, CSV, TXT) or connect to external data sources (Microsoft Fabric, SQL databases, Azure Synapse, ODBC, or an existing Azure AI Search index). The platform extracts knowledge using AI and lets users explore results through natural language chat and auto-generated dashboards. Deploy with one command (`azd up`), bring your data, start asking questions.

**Why we built it.** Every team has data they wish they could just talk to — call transcripts, contracts, research papers, support tickets, patient records, policy documents. But building a knowledge mining solution from scratch for each use case takes months. This accelerator eliminates that. Deploy once, bring whatever data you have, and the platform adapts. The dashboards, filters, chat behavior, and processing pipelines all shape themselves to your content. No domain-specific code, no hardcoded schemas.

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
- **Document ingestion** — Users upload files, the system processes them in the background (extract text → split into chunks → create embeddings → add to search index). The upload response is instant
- **External data connectors** — Connect to Fabric, SQL databases, Synapse, ODBC sources, or an existing Azure AI Search index. The system figures out which columns map to which fields. Can pull data in, query live, or both
- **Hybrid search** — Combines keyword matching and semantic similarity for better results
- **RAG chat** — Users ask questions in natural language, the system finds relevant content and GPT-4o generates an answer with citations
- **Insights engine** — Looks at what data you have, decides which charts and KPIs are useful, and builds a dashboard automatically. No hardcoded charts — adapts to any dataset
- **Pipeline engine** — Lets you define multi-step processing workflows in YAML (e.g., classify → summarize → extract entities). Runs automatically when new data arrives, tracks history, and shows progress in real time
- **Auth** — Azure AD login via App Service EasyAuth, with role-based access control

### Frontend (React / Fluent UI)
- **Home** — Landing page where users drag-and-drop files or see the status of their data. Shows which files are still processing and which are ready to explore
- **Explore** — The main chat experience. Users type questions in plain English, get answers grounded in their data with clickable source citations. They can filter by topic, sentiment, date, etc. and save conversations for later
- **Insights** — A dashboard that builds itself based on your data. Users see KPIs, charts (donut, bar, line, word cloud), and key findings without configuring anything. They can filter and drill down
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
