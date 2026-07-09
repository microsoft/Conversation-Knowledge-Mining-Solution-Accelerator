# Conversation knowledge mining solution accelerator

Gain actionable insights from large volumes of conversational data by identifying key themes, patterns, and relationships. Using Microsoft Foundry, Azure Content Understanding, Azure OpenAI Service, and Foundry IQ, this solution analyzes unstructured dialogue and maps it to meaningful, structured insights.

Capabilities such as topic modeling, key phrase extraction, speech-to-text transcription, and interactive chat enable users to explore data naturally and make faster, more informed decisions.

<div align="center">

[**SOLUTION OVERVIEW**](#solution-overview)  |  [**QUICK DEPLOY**](#quick-deploy)  |  [**SCENARIO PACKS**](#scenario-packs)  |  [**BUSINESS SCENARIO**](#business-scenario)  |  [**SUPPORTING DOCUMENTATION**](#supporting-documentation)

</div>

> **Note:** With any AI solutions you create using these templates, you are responsible for assessing all associated risks and for complying with all applicable laws and safety standards.

---

## Solution Overview

This solution processes conversational and enterprise content data — PDFs, DOCX, images, JSON, CSV, TXT, SQL databases, handwritten text, charts, tables, and form fields — and makes it explorable through conversational chat, auto-generated dashboards, and configurable processing pipelines. The platform is fully use-case agnostic: the same deployment that analyzes call center transcripts can analyze legal contracts, research papers, insurance claims, or any other content.

### Solution Architecture

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
            │  GPT-5.1 + ada-2 │                    │  Search     │   │  Understanding   │
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

### Document Processing Pipeline

```
Upload (instant response)
  → Azure Blob Storage (raw file)
  → Queue: extraction
       → Azure Content Understanding (text, summary, topics, key phrases)
       → Queue: enrichment
            → Chunk text (1000 chars, 200 overlap, paragraph-aware)
            → Generate embeddings (text-embedding-ada-002, 1536 dims, cached)
            → Index chunks + vectors in Azure AI Search (HNSW, upserts)
            → Status → "ready"
```

### Key Features

<details open>
<summary>Click to learn more about the key features this solution enables</summary>

- **Mined entities and relationships**
  Azure Content Understanding and Azure OpenAI extract entities, topics, and relationships from unstructured conversations to build a richer knowledge base.

- **Processed data at scale**
  The pipeline processes high-volume conversation data, generates embeddings, and indexes results for fast hybrid retrieval using RAG patterns.

- **Visualized insights**
  An interactive dashboard surfaces trends, distributions, and outliers so teams can quickly move from raw conversation logs to actionable understanding.

- **Natural language interaction**
  Users can ask contextual questions, follow up on findings, and get grounded responses with citations through an intuitive chat experience.

- **Actionable insights**
  Key phrase extraction, summarization, topic modeling, and sentiment signals support faster decision-making across operations and support workflows.

- **Async document processing**
  A two-stage queue pipeline keeps uploads responsive while extraction and enrichment run in the background with retry support.

- **LLM-planned insights dashboard**
  The system analyzes your data schema, then plans and computes relevant KPIs and charts automatically for each dataset.

- **Configurable processing pipelines**
  YAML-defined pipelines with 11 pluggable capabilities (classify, summarize, extract entities, filter, generate, search, select, embed, transform, etc.). Auto-trigger on upload or run manually.

- **Dynamic filter generation**
  Filters are generated automatically from your data's actual metadata fields and values — not predefined. Different datasets produce different filter panels. The system analyzes document metadata to discover categorical dimensions (e.g., sentiment, topic, category) and creates interactive filters for each.

- **Document explorer**
  Browse individual documents, search across your corpus, open a document, and ask for on-the-fly summaries or entity extraction (people, places, topics).

- **Bring Your Own Index**
  Connect an existing Azure AI Search index during post-deployment setup and immediately chat with it — no upload needed.

- **Bring Your Own Data**
  Connect external databases (Microsoft Fabric, SQL, Azure Synapse) during post-deployment setup with auto-detected field mapping and one-click ingestion.


</details>

### How It Adapts to Any Use Case

There is zero domain-specific logic in the codebase. The platform adapts automatically to whatever data you provide:

| What adapts | How |
|-------------|-----|
| **Dashboard charts & KPIs** | The insights engine reads your data's schema and values, then uses GPT-5.1 to decide which visualizations make sense. |
| **Search filters** | Filters are generated from your data's actual fields and values — not predefined. Different datasets produce different filter panels. |
| **Chat grounding** | RAG retrieval works on whatever content is indexed. The system prompt is configurable via `prompts.yaml`. |
| **Field mapping** | When connecting a data source, the system auto-detects which columns are the ID, text body, title, timestamp, etc. |

---

## Quick Deploy

### Prerequisites

- Azure subscription with permissions to create resource groups, resources, and assign roles
- [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) >= 1.18.0
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for container-based deployment)

### How to Deploy

1. Clone the repository and navigate to the project root

2. Login to Azure:
   ```bash
   azd auth login
   ```

3. Deploy all resources:
   ```bash
   azd up
   ```
   After provisioning, the post-deployment script will:
   - Set up the AI agent automatically
   - Present an interactive menu to choose a scenario pack or connect a data source

   You can also run the data setup separately:
   ```bash
   # Run interactively to choose from a menu
   ./scripts/setup-data.ps1

   # Or specify directly
   ./scripts/setup-data.ps1 -Scenario contact-center
   ./scripts/setup-data.ps1 -Scenario mortgage-application
   ./scripts/setup-data.ps1 -Scenario telecom-analysis
   ```

4. (Optional) Configure authentication:
   - Go to Azure Portal → App Service → **Authentication** → **Add identity provider** → **Microsoft**

After deploying, the Home page is ready for your data — upload files or load a scenario pack to get started:

![Home page after deployment](docs/images/homepage-ui.png)

> ⚠️ **Important:** To avoid unnecessary costs, remember to take down your app if it's no longer in use by running `azd down`.

---

## Scenario Packs

After deploying with `azd up`, the post-deployment script presents an interactive menu to seed data. You can choose a built-in scenario pack, connect an external data source, or skip and upload documents from the web UI later.

All options are defined in [`data/config/scenarios.json`](data/config/scenarios.json) and can be extended.

### Built-in Scenarios

| # | Scenario | Data folder | Sample data | What users see |
|---|----------|-------------|-------------|----------------|
| 1 | **Contact Center** | `data/ContactCenter_usecase/` | JSON call transcripts (5 conversations) + pre-processed search index data | Sentiment trends, topic clusters, agent performance, Q&A over conversations |
| 2 | **Mortgage Application** | `data/MortgageApplication_usecase/` | PDF documents (housing reports, purchase contracts, NPL reports) | Document summarization, clause extraction, risk analysis, Q&A over mortgage docs |
| 3 | **Telecom Analysis** | `data/telecom_analysis_usecase/` | JSON call transcripts (5) + WAV audio recordings (5) | Call analysis, audio transcription, sentiment breakdowns, topic clustering |

### Connect External Data Sources

These options are also available in the post-deployment menu. No data movement — the app queries your source at runtime.
Currently supported connectors are Azure AI Search and Microsoft Fabric.

| # | Source | What you provide |
|---|--------|-----------------|
| 4 | **Azure AI Search** | Search endpoint + index name |
| 5 | **Microsoft Fabric** | SQL endpoint + database + table name |

> Note: SQL Database and Azure Synapse connector options were removed from the setup menu in this branch.

#### Azure AI Search input tips

When you choose `4. Azure AI Search (connect)` in `./scripts/setup-data.ps1`:

1. Enter your search service endpoint when prompted, for example:
  `https://my-search.search.windows.net`
2. For index name:
  - Press Enter to auto-discover indexes, or
  - Type the index name directly.
3. If auto-discovery reports no indexes, verify the endpoint is correct and then enter the index name manually.

Equivalent non-interactive command:

```bash
./scripts/setup-data.ps1 -ExternalSource azure_search -Name "My Index" -Endpoint "https://my-search.search.windows.net" -Table "my-index"
```

### Bring Your Own Data

Upload files directly from the web UI after deployment. Supported formats: PDF, DOCX, images, JSON, CSV, TXT, and audio (WAV, MP3).

> ⚠️ The sample data used in this repository is synthetic and generated using Azure OpenAI service. The data is intended for use as sample data only.

### Adding Custom Scenarios and Data Sources

Custom scenarios are configuration-driven via [`data/config/scenarios.json`](data/config/scenarios.json).
Custom data source connectors require script and adapter updates in this branch (only Azure AI Search and Microsoft Fabric are implemented end-to-end).

#### Add a new scenario pack

1. Create a folder under `data/` for your data (e.g. `data/Insurance_usecase/`)
2. Add your files — JSON transcripts, PDFs, DOCX, images, etc.
3. Add an entry to the `scenarios` object in `data/config/scenarios.json`:

```json
"insurance-claims": {
  "name": "Insurance Claims",
  "description": "Claims documents — fraud detection, severity classification, processing time analysis",
  "data_folder": "Insurance_usecase",
  "data_types": ["pdf", "docx"],
  "has_preprocessed": false
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name shown in the setup menu |
| `description` | Yes | One-line description shown below the menu option |
| `data_folder` | Yes | Subfolder name under `data/` containing your files |
| `data_types` | Yes | Array of file extensions (e.g. `["json"]`, `["pdf", "docx"]`) |
| `has_preprocessed` | Yes | Set to `true` if your data includes pre-computed embeddings and enrichments |
| `preprocessed_files` | Only if `has_preprocessed` is `true` | Object with paths to `search_index`, `processed_data`, and `key_phrases` files |

If you have pre-enriched data (embeddings, sentiments, topics already computed), set `has_preprocessed: true` and specify the file paths:

```json
"my-scenario": {
  "name": "My Scenario",
  "description": "Pre-enriched dataset with embeddings",
  "data_folder": "MyData_usecase",
  "data_types": ["json"],
  "has_preprocessed": true,
  "preprocessed_files": {
    "search_index": "sample_search_index_data.json",
    "processed_data": "sample_processed_data.json",
    "key_phrases": "sample_processed_data_key_phrases.json"
  }
}
```

#### Add a new external data source

The setup menu reads data source labels from `data/config/scenarios.json`, but a working connector also needs implementation updates.

To add a connector that actually works, update all of the following:

1. Add the source in [`data/config/scenarios.json`](data/config/scenarios.json) under `data_sources`.
2. Extend source handling in [`scripts/connect-data.py`](scripts/connect-data.py):
  - `SOURCE_TYPES`
  - `adapter_map`
  - argparse `--type` choices
3. Extend accepted source types in [`scripts/connect-data.ps1`](scripts/connect-data.ps1) and [`scripts/setup-data.ps1`](scripts/setup-data.ps1).
4. Implement the backend connector in [`src/api/modules/data_sources`](src/api/modules/data_sources) and ensure `test_connection` works.

Example `data_sources` entry (menu metadata):

```json
"my_source": {
  "name": "My Data Source",
  "description": "Connect a custom source",
  "fields": ["endpoint", "database", "table"],
  "prompts": {
    "endpoint": "Service endpoint",
    "database": "Database name",
    "table": "Table name"
  }
}
```

If you only need the currently supported connectors, use:

```bash
./scripts/connect-data.ps1 -Type azure_search
./scripts/connect-data.ps1 -Type fabric
```

After editing `scenarios.json`, run the setup script to validate the menu updates:

```bash
./scripts/setup-data.ps1
```

---

### Local Development

**Backend:**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r src/api/requirements.txt
./scripts/start-local-backend.ps1
```

For single-process local development on Windows, prefer [scripts/start-local-backend.ps1](scripts/start-local-backend.ps1). It stops any existing listener on port 8000 before starting the API and avoids `--reload` by default, which is more stable on Windows.

**Frontend:**
```bash
cd src/app
npm install
REACT_APP_API_BASE_URL=http://localhost:8000/api npm start
```

**Docker:**
```bash
docker-compose up --build
```

> **Note:** For local development with Azure Queue processing, assign yourself the **Storage Queue Data Contributor** role on the storage account. Without it, the queue worker falls back to in-process background tasks.

> **Note:** To allow setup scripts to fall back to deployed Azure backend if local health check fails (useful for CI/CD), set `KM_ALLOW_DEPLOYED_BACKEND_FALLBACK=1`.

### Azure Services and Costs

Check the [Azure Products by Region](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/?products=all&regions=all) page and select a region where the following services are available.

| Service | Purpose | Pricing |
|---------|---------|---------|
| [Azure AI Services (OpenAI)](https://learn.microsoft.com/azure/cognitive-services/openai/overview) | Chat (GPT-5.1), embeddings (ada-002), summarization | [Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/) |
| [Azure AI Search](https://learn.microsoft.com/azure/search/search-what-is-azure-search) | Hybrid search (BM25 + HNSW vector) for document retrieval | [Pricing](https://azure.microsoft.com/pricing/details/search/) |
| [Azure AI Foundry](https://learn.microsoft.com/azure/ai-studio/what-is-ai-studio) | Agent orchestration with intelligent tool routing (search vs. SQL), centralized governance, tracing, and quotas | [Pricing](https://azure.microsoft.com/pricing/details/ai-studio/) |
| [Azure App Service](https://learn.microsoft.com/azure/app-service/overview) | Hosts backend API and frontend web application | [Pricing](https://azure.microsoft.com/pricing/details/app-service/linux/) |
| [Azure Storage Account](https://learn.microsoft.com/azure/storage/common/storage-account-overview) | Blob storage for documents, Queue storage for async processing | [Pricing](https://azure.microsoft.com/pricing/details/storage/blobs/) |
| [Azure SQL Database](https://learn.microsoft.com/azure/azure-sql/database/sql-database-paas-overview) | Primary database — structured data, chat history, metadata, enrichment cache | [Pricing](https://azure.microsoft.com/pricing/details/azure-sql-database/single/) |
| [Azure Cosmos DB](https://learn.microsoft.com/azure/cosmos-db/introduction) | Optional alternative database — set `DATABASE_PROVIDER=cosmos` in `.env` | [Pricing](https://azure.microsoft.com/pricing/details/cosmos-db/autoscale-provisioned/) |

---

## Business Scenario

In large organizations, it's difficult and time-consuming to analyze large volumes of unstructured data. Traditional tools limit interaction with data, making it hard to surface patterns or ask follow-up questions without extensive manual exploration.

This solution addresses those challenges by enabling:

- **Natural language interaction** — Ask questions about your documents using conversational chat
- **Automated extraction** — AI extracts entities, relationships, and key information from unstructured content
- **Adaptive dashboards** — The insights engine reads your data and auto-generates relevant charts, KPIs, and key findings
- **Interactive exploration** — Dynamic filters and structured insights help users navigate large datasets
- **Faster decision-making** — Summarized, contextualized data reduces manual analysis effort

> ⚠️ The sample data used in this repository is synthetic and generated using Azure OpenAI service. The data is intended for use as sample data only.

---

## Supporting Documentation

### Tech Stack

| Component | Product | Why |
|-----------|---------|-----|
| Backend API | **FastAPI** | Async-native, auto-generated OpenAPI docs, dependency injection |
| Frontend | **React + Fluent UI 2** | Microsoft design system, accessible components, TypeScript |
| LLM (chat + insights) | **Azure OpenAI GPT-5.1** | model for grounded Q&A and reasoning |
| Embeddings | **text-embedding-ada-002** | Proven embedding model, 1536 dims, good cost/quality ratio |
| Vector + keyword search | **Azure AI Search** | Hybrid search (BM25 + HNSW) in one service, managed |
| Document extraction | **Azure Content Understanding** | Handles PDF, images, handwriting, tables — multi-modal |
| Agent orchestration | **Azure AI Foundry** | Managed agent service with tool support |
| Intelligent tool routing | **Agent Framework** (`agent_framework`, `agent_framework_openai`) | Python framework for binding tools, intelligent routing, and multi-turn agentic workflows |
| LLM client layer | **Foundry IQ (`azure-ai-projects`)** | All model access goes through a single Foundry Project for centralized governance, tracing, and quotas |
| Structured data | **Azure SQL Database** (default) | Primary database — metadata, chat history, enrichment cache, data source configs |
| Structured data (alt) | **Azure Cosmos DB** (optional) | Alternative database — set `DATABASE_PROVIDER=cosmos` |
| File + queue storage | **Azure Blob + Queue** | Raw file storage + async job queue for the processing pipeline |
| Auth | **App Service EasyAuth** | Zero-code Azure AD integration |



### Security Guidelines

This solution uses [Managed Identity](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/overview) for secure access to Azure resources, eliminating the need for hard-coded credentials. All Azure service communication uses RBAC — no API keys in app config.

To maintain strong security practices:
- Enable [GitHub secret scanning](https://docs.github.com/code-security/secret-scanning/about-secret-scanning) in your repository
- Consider enabling [Microsoft Defender for Cloud](https://learn.microsoft.com/azure/defender-for-cloud/) to monitor Azure resources
- Use [Virtual Networks](https://learn.microsoft.com/azure/app-service/overview-vnet-integration) for production deployments

---

## Sample Questions

Use these sample questions to explore each scenario after loading its data.

### Contact Center

1. Please provide the total number of calls by date for last 7 days
2. Provide a summary of performance issues users reported this week
3. Turn these key topics into a structured FAQ

### Telecom Analysis

1. Total number of calls by date for last 7 days
2. What are top 7 challenges user reported?
3. What are the top recommendations to reduce these customer challenges?

### Mortgage Application

1. What are the key findings in the Annual Housing Report?
2. What does the report say about accessibility in housing?

---

## Provide Feedback

Have questions, find a bug, or want to request a feature? [Submit a new issue](https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/issues) on this repo.

---

## Responsible AI Transparency FAQ

For responsible AI transparency details, see:
- [Azure AI Foundry Agent Service transparency note](https://learn.microsoft.com/azure/ai-foundry/responsible-ai/agents/transparency-note)
- [Agent Framework transparency FAQ](https://github.com/microsoft/agent-framework/blob/main/TRANSPARENCY_FAQ.md)

---

## Disclaimers

This release is an artificial intelligence (AI) system that generates text in response to user queries. The system is designed to answer questions **only** from documents that have been uploaded to the platform. It does not search the web, use external data sources, or generate responses from its general training data.

While the system is designed to ground all responses in the uploaded documents, AI-generated outputs may occasionally contain inaccuracies. Users are responsible for verifying the accuracy and suitability of any content generated by the system.

To the extent that the Software includes components or code used in or derived from Microsoft products or services, you must also comply with the Product Terms applicable to such Microsoft Products and Services.

You must also comply with all domestic and international export laws and regulations that apply to the Software. For further information on export restrictions, visit https://aka.ms/exporting.

BY ACCESSING OR USING THE SOFTWARE, YOU ACKNOWLEDGE THAT THE SOFTWARE IS NOT DESIGNED OR INTENDED TO SUPPORT ANY USE IN WHICH A SERVICE INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE COULD RESULT IN THE DEATH OR SERIOUS BODILY INJURY OF ANY PERSON OR IN PHYSICAL OR ENVIRONMENTAL DAMAGE (COLLECTIVELY, "HIGH-RISK USE"), AND THAT YOU WILL ENSURE THAT, IN THE EVENT OF ANY INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE, THE SAFETY OF PEOPLE, PROPERTY, AND THE ENVIRONMENT ARE NOT REDUCED BELOW A LEVEL THAT IS REASONABLY, APPROPRIATE, AND LEGAL, WHETHER IN GENERAL OR IN A SPECIFIC INDUSTRY.
