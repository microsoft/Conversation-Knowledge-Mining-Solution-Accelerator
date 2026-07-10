# Conversation Knowledge Mining Solution Accelerator

This solution accelerator leverages **Microsoft Foundry**, **Azure Content Understanding**, **Azure OpenAI Service**, and **Foundry IQ** to enable organizations to derive insights from volumes of conversational data using generative AI. It offers **key phrase extraction**, **topic modeling**, and **interactive chat experiences** through an intuitive web interface.

Gain actionable insights from large volumes of conversational data by identifying key themes, patterns, and relationships. This solution analyzes unstructured dialogue and maps it to meaningful, structured insights, enabling analysts to extract understanding through natural language interaction. It supports tasks like identifying customer support trends, improving contact center quality, and uncovering operational intelligence — allowing teams to spot patterns, act on feedback, and make informed decisions faster.

<br/>

<div align="center">

[**SOLUTION OVERVIEW**](#solution-overview)  |  [**ARCHITECTURE**](#architecture)  |  [**QUICK DEPLOY**](#quick-deploy)  |  [**INDUSTRY SCENARIOS**](#industry-scenarios)  |  [**BUSINESS SCENARIO**](#business-scenario)  |  [**SUPPORTING DOCUMENTATION**](#supporting-documentation)

</div>

<br/>

> **Note:** With any AI solutions you create using these templates, you are responsible for assessing all associated risks and for complying with all applicable laws and safety standards. Learn more in the transparency documents for [Agent Service](https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-ai/agents/transparency-note) and [Agent Framework](https://github.com/microsoft/agent-framework/blob/main/TRANSPARENCY_FAQ.md).

<br/>

---

## Solution Overview

This solution turns any conversational or enterprise dataset into an interactive, insight-driven experience. Files are uploaded or connected, processed through an AI extraction pipeline, and made explorable through three integrated surfaces: **Home** (upload and manage data), **Explore** (chat with your data using a Foundry-hosted agent), and **Insights** (auto-generated KPI dashboards driven by LLM schema analysis).

The platform is fully scenario-agnostic. The same deployment handles call center transcripts, mortgage documents, telecom recordings, or any structured or unstructured content — no domain-specific code changes required.

### Solution Architecture

![Solution Architecture](docs/images/architecture.svg)

### How It Works

**Home** — Upload files (PDF, DOCX, JSON, CSV, WAV, images) or run `./scripts/setup-data.ps1` to load a built-in sample scenario pack. The upload is acknowledged instantly; processing runs in the background.

**Processing pipeline** — Azure Content Understanding extracts text, summary, topics, and key phrases. Results are stored in Azure SQL. Embeddings are generated using ada-002 and indexed in Azure AI Search (hybrid HNSW + BM25).

**Explore** — Converse with your data. Questions are routed to a Microsoft Foundry ChatAgent with two tools: Azure AI Search (semantic retrieval) and SQL (structured analytics). The agent reasons across both, then returns a grounded, structured answer. Chat history is multi-turn and persisted per session.

**Insights** — The LLM reads your dataset's schema (field names, cardinality, semantic types) and generates a plan for KPIs and charts. SQL queries run against your actual data. The result is an adaptive dashboard — layouts, filters, and metrics are all data-driven, not hard-coded.

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

- **Mined entities and relationships** <br/>
  Azure Content Understanding and Azure OpenAI extract entities, topics, and relationships from unstructured conversations to build a richer knowledge base.

- **Processed data at scale** <br/>
  The pipeline processes high-volume conversation data, generates embeddings, and indexes results for fast hybrid retrieval using RAG patterns.

- **Visualized insights** <br/>
  An interactive dashboard surfaces trends, distributions, and outliers so teams can quickly move from raw conversation logs to actionable understanding.

- **Natural language interaction** <br/>
  Users can ask contextual questions, follow up on findings, and get grounded responses with citations through an intuitive chat experience.

- **Actionable insights** <br/>
  Key phrase extraction, summarization, topic modeling, and sentiment signals support faster decision-making across operations and support workflows.

- **LLM-planned insights dashboard** <br/>
  The system analyzes your data schema, then plans and computes relevant KPIs and charts automatically for each dataset.

- **Configurable processing pipelines** <br/>
  YAML-defined pipelines with pluggable capabilities (classify, summarize, extract entities, filter, generate, search, embed, transform, and more). Auto-trigger on upload or run manually.

- **Dynamic filter generation** <br/>
  Filters are generated from your data's actual metadata fields and values — not predefined. Different datasets produce different filter panels.

- **Bring Your Own Index / Data** <br/>
  Connect an existing Azure AI Search index or external database (Microsoft Fabric, SQL) without uploading data again.

</details>

<br/>

---

## Quick Deploy

### Prerequisites

- Azure subscription with permissions to create resource groups, resources, and assign roles
- [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) >= 1.18.0
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

> ⚠️ **Important: Check Azure OpenAI Quota Availability** <br/>
> To ensure sufficient quota is available in your subscription, please verify quota before you deploy. Here are some example regions where the services are available: East US, East US2, Australia East, UK South, France Central.

### How to Deploy

1. Clone the repository and navigate to the project root.

2. Login to Azure:
   ```bash
   azd auth login
   ```

3. Deploy all resources:
   ```bash
   azd up
   ```
   The post-deployment script will set up the AI agent and present a menu to choose a scenario or connect a data source.

4. Optionally run data setup separately using the interactive menu:
   ```bash
   ./scripts/setup-data.ps1
   ```
   
   Or load a specific scenario directly:
   ```bash
   ./scripts/setup-data.ps1 -Scenario contact-center
   ./scripts/setup-data.ps1 -Scenario mortgage-application
   ./scripts/setup-data.ps1 -Scenario telecom-analysis
   ```
   
   See **[Industry scenarios](#industry-scenarios)** below for scenario descriptions and additional options (Azure AI Search, Microsoft Fabric, or upload files manually).

5. Optionally configure authentication in Azure Portal → App Service → **Authentication** → **Add identity provider** → **Microsoft**.

After deploying, the Home page is ready for your data:

![Home page after deployment](docs/images/homepage-ui.png)

> ⚠️ **Important:** To avoid unnecessary costs, remember to take down your app if it's no longer in use by running `azd down`.

### Local Development

**Backend:**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r src/api/requirements.txt
uvicorn src.api.main:app --reload --port 8000
```

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

### Azure Services and Costs

Pricing varies by region and usage. Use the [Azure pricing calculator](https://azure.microsoft.com/pricing/calculator) to estimate costs for your subscription.

| Service | Purpose | Pricing |
|---------|---------|---------|
| [Azure AI Services (OpenAI)](https://learn.microsoft.com/azure/cognitive-services/openai/overview) | Chat (GPT-5.1), embeddings (ada-002), summarization | [Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/) |
| [Azure AI Foundry](https://learn.microsoft.com/azure/ai-studio/what-is-ai-studio) | Agent orchestration, centralized governance, tracing, and quotas | [Pricing](https://azure.microsoft.com/pricing/details/ai-studio/) |
| [Foundry IQ / Azure AI Search](https://learn.microsoft.com/azure/search/search-what-is-azure-search) | Hybrid search (BM25 + HNSW vector) for document retrieval | [Pricing](https://azure.microsoft.com/pricing/details/search/) |
| [Azure App Service](https://learn.microsoft.com/azure/app-service/overview) | Hosts backend API and frontend web application | [Pricing](https://azure.microsoft.com/pricing/details/app-service/linux/) |
| [Azure Storage Account](https://learn.microsoft.com/azure/storage/common/storage-account-overview) | Blob storage for documents, Queue storage for async processing | [Pricing](https://azure.microsoft.com/pricing/details/storage/blobs/) |
| [Azure SQL Database](https://learn.microsoft.com/azure/azure-sql/database/sql-database-paas-overview) | Structured data — metadata, chat history, enrichment cache | [Pricing](https://azure.microsoft.com/pricing/details/azure-sql-database/single/) |
| [Azure Cosmos DB](https://learn.microsoft.com/azure/cosmos-db/introduction) | Optional: chat history and sessions | [Pricing](https://azure.microsoft.com/pricing/details/cosmos-db/autoscale-provisioned/) |
| [Azure Monitor / Log Analytics](https://learn.microsoft.com/azure/azure-monitor/logs/log-analytics-overview) | Telemetry and logs | [Pricing](https://azure.microsoft.com/pricing/details/monitor/) |

<br/>

---

## Industry scenarios

The solution is fully data-driven and can be adapted to any industry. After deployment, use the data setup script to populate your platform with one of three built-in sample scenario packs, connect an external data source, or upload your own files.

### Built-in Sample Scenario Packs

| Scenario | Demonstrates | Files |
|----------|--------------|-------|
| **Contact Center** | Sentiment analysis, topic clustering, agent performance, conversational search | JSON call transcripts + pre-processed search index |
| **Mortgage Application** | Document summarization, clause extraction, risk analysis | PDF documents (housing reports, contracts) |
| **Telecom Analysis** | Audio transcription, sentiment analysis, topic clustering | JSON transcripts + WAV audio recordings |

### Other Options

**Option 1 — Load a sample scenario pack** (recommended to start)
```bash
./scripts/setup-data.ps1                              # interactive menu to choose
./scripts/setup-data.ps1 -Scenario contact-center
./scripts/setup-data.ps1 -Scenario mortgage-application
./scripts/setup-data.ps1 -Scenario telecom-analysis
```

**Option 2 — Connect an existing Azure AI Search index**

Reuse an existing search index without uploading data:
```bash
./scripts/setup-data.ps1 -ExternalSource azure_search -Name "My Index" -Endpoint "https://my-search.search.windows.net" -Table "my-index"
```

**Option 3 — Connect Microsoft Fabric**

Connect a Fabric Lakehouse or Warehouse using its SQL endpoint:
```bash
./scripts/setup-data.ps1 -ExternalSource fabric -Name "My Warehouse" -Endpoint "your-server.database.fabric.microsoft.com" -Database "MyWarehouse" -Table "MyTable"
```

**Option 4 — Upload your own files later**

Skip setup and upload data directly from the web application. Supported formats: PDF, DOCX, JSON, CSV, TXT, images, WAV, MP3.

<br/>

---

## Business Scenario

Analysts often work with large volumes of unstructured conversational data, making it difficult to extract actionable insights quickly and accurately. Traditional tools limit interaction with data, making it hard to surface patterns or ask the right follow-up questions without extensive manual exploration.

This solution addresses those challenges by enabling:

- **Natural language interaction** — Ask questions about your documents using conversational chat
- **Automated extraction** — AI extracts entities, relationships, and key information from unstructured content
- **Adaptive dashboards** — The insights engine reads your data and auto-generates relevant charts, KPIs, and key findings
- **Interactive exploration** — Dynamic filters and structured insights help users navigate large datasets
- **Faster decision-making** — Summarized, contextualized data reduces manual analysis effort

<details>
<summary>Click to learn more about business value</summary>

- **Better decision-making** — Summarized, contextualized data helps organizations make informed strategic decisions that drive operational improvements at scale.
- **Time saved** — Automated insight extraction and scalable data exploration reduce manual analysis efforts.
- **Interactive data insights** — Employees can engage directly with conversational data using natural language.
- **Actionable insights** — Clear, contextual insights empower employees to take meaningful action based on data-driven evidence.

</details>

<details>
<summary>Click to learn more about use cases</summary>

| **Use case** | **Persona** | **Summary** |
|---|---|---|
| Contact Center Customer Support | Analyst | Contextualized insights from mined data that enables employees to solve problems and take action. Interactive data that allows employees to ask questions and receive timely responses. |
| IT Helpdesk | IT Helpdesk Analyst | AI-generated insights from call data, common issue identification, FAQ content generation — transforming a labor-intensive review into a fast, accurate workflow. |
| Mortgage & Lending | Loan Analyst | Document summarization, clause extraction, and risk analysis across housing reports and purchase contracts. |
| Telecom Operations | Operations Analyst | Call analysis, audio transcription, sentiment breakdowns, and topic clustering across call transcripts and recordings. |

</details>

<br/>

---

## Supporting Documentation

### Tech Stack

| Component | Product |
|-----------|---------|
| Backend API | **FastAPI** (Python) |
| Frontend | **React + Fluent UI 2** (TypeScript) |
| LLM (chat + insights) | **Azure OpenAI GPT-5.1** |
| Embeddings | **text-embedding-ada-002** |
| Vector + keyword search | **Azure AI Search** (BM25 + HNSW) |
| Document extraction | **Azure Content Understanding** |
| Agent orchestration | **Azure AI Foundry** |
| Agent framework | **agent_framework** + **agent_framework_openai** |
| LLM client layer | **Foundry IQ** (`azure-ai-projects`) |
| Primary database | **Azure SQL Database** |
| Optional database | **Azure Cosmos DB** |
| File + queue storage | **Azure Blob + Queue** |
| Auth | **App Service EasyAuth** (Azure AD) |

### Security Guidelines

This solution uses [Managed Identity](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/overview) for secure access to Azure resources, eliminating the need for hard-coded credentials. All Azure service communication uses RBAC.

Additional recommendations:
- Enable [GitHub secret scanning](https://docs.github.com/code-security/secret-scanning/about-secret-scanning)
- Enable [Microsoft Defender for Cloud](https://learn.microsoft.com/azure/defender-for-cloud/)
- Use [Virtual Networks](https://learn.microsoft.com/azure/app-service/overview-vnet-integration) for production deployments

### Sample Questions

**Contact Center**
1. Please provide the total number of calls by date for last 7 days
2. Provide a summary of performance issues users reported this week
3. Turn these key topics into a structured FAQ

**Telecom Analysis**
1. Total number of calls by date for last 7 days
2. What are top 7 challenges users reported?
3. What are the top recommendations to reduce these customer challenges?

**Mortgage Application**
1. What are the key findings in the Annual Housing Report?
2. What does the report say about accessibility in housing?

### Cross References

| Solution Accelerator | Description |
|---|---|
| [Document Knowledge Mining](https://github.com/microsoft/Document-Knowledge-Mining-Solution-Accelerator) | Identify relevant documents, summarize unstructured information, and generate document templates. |
| [Content Processing](https://github.com/microsoft/document-generation-solution-accelerator) | Extracts data from multi-modal content, maps it to schemas with confidence scoring and user validation. |

<br/>

---

## Provide Feedback

Have questions, find a bug, or want to request a feature? [Submit a new issue](https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/issues) on this repo and we'll connect.

<br/>

---

## Responsible AI Transparency FAQ

Please refer to the following transparency documents for responsible AI details:
- [Azure AI Foundry Agent Service transparency note](https://learn.microsoft.com/azure/ai-foundry/responsible-ai/agents/transparency-note)
- [Agent Framework transparency FAQ](https://github.com/microsoft/agent-framework/blob/main/TRANSPARENCY_FAQ.md)

<br/>

---

## Disclaimers

To the extent that the Software includes components or code used in or derived from Microsoft products or services, including without limitation Microsoft Azure Services (collectively, "Microsoft Products and Services"), you must also comply with the Product Terms applicable to such Microsoft Products and Services. You acknowledge and agree that the license governing the Software does not grant you a license or other right to use Microsoft Products and Services. Nothing in the license or this ReadMe file will serve to supersede, amend, terminate or modify any terms in the Product Terms for any Microsoft Products and Services.

You must also comply with all domestic and international export laws and regulations that apply to the Software, which include restrictions on destinations, end users, and end use. For further information on export restrictions, visit https://aka.ms/exporting.

You acknowledge that the Software and Microsoft Products and Services (1) are not designed, intended or made available as a medical device(s), and (2) are not designed or intended to be a substitute for professional medical advice, diagnosis, treatment, or judgment and should not be used to replace or as a substitute for professional medical advice, diagnosis, treatment, or judgment. Customer is solely responsible for displaying and/or obtaining appropriate consents, warnings, disclaimers, and acknowledgements to end users of Customer's implementation of the Online Services.

BY ACCESSING OR USING THE SOFTWARE, YOU ACKNOWLEDGE THAT THE SOFTWARE IS NOT DESIGNED OR INTENDED TO SUPPORT ANY USE IN WHICH A SERVICE INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE COULD RESULT IN THE DEATH OR SERIOUS BODILY INJURY OF ANY PERSON OR IN PHYSICAL OR ENVIRONMENTAL DAMAGE (COLLECTIVELY, "HIGH-RISK USE"), AND THAT YOU WILL ENSURE THAT, IN THE EVENT OF ANY INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE, THE SAFETY OF PEOPLE, PROPERTY, AND THE ENVIRONMENT ARE NOT REDUCED BELOW A LEVEL THAT IS REASONABLY, APPROPRIATE, AND LEGAL, WHETHER IN GENERAL OR IN A SPECIFIC INDUSTRY.
