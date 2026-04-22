# Knowledge Mining Solution Accelerator

Ingest, extract, and classify content from a high volume of documents to gain deeper insights and generate relevant suggestions for quick and easy reasoning. This enables the ability to conduct chat-based insight discovery, analysis, and receive structured outputs from your data.

[SOLUTION OVERVIEW](#solution-overview) | [QUICK DEPLOY](#quick-deploy) | [BUSINESS USE CASE](#business-use-case) | [SUPPORTING DOCUMENTATION](#supporting-documentation)

---

## Solution Overview

This solution leverages Azure OpenAI, Azure Content Understanding, and Azure AI Search in a hybrid approach by combining OCR, multi-modal LLM extraction, and retrieval-augmented generation (RAG) to extract information from documents and provide insights — including text documents, handwritten text, charts, graphs, tables, and form fields.

### Solution Architecture

```
                                                    ┌──────────────────┐
                                                    │  Azure AI Search │
                                                    │  Save Chunks /   │
                                                    │  Vectors /       │
                                                    │  Keywords        │
                                                    └────────▲─────────┘
                                                             │
┌──────────┐    HTTP     ┌──────────────────┐    ┌───────────┴───────────┐    ┌─────────────────────┐
│          │   Invoke    │                  │    │                       │    │  Content             │
│  Client  │────────────▶│   Web App        │    │   Document            │───▶│  Understanding       │
│ (Browser)│◀────────────│   React 18       │    │   Processor           │    │  Extract Contents /  │
│          │             │   Fluent UI      │    │   (FastAPI)           │    │  Content from Files  │
└──────────┘             │                  │    │                       │    └─────────────────────┘
                         │  • Doc Search    │    │  • Upload & parse     │
                         │  • Process       │────▶  • CU extraction     │    ┌─────────────────────┐
                         │  • Chat          │HTTP│  • Enrich & index     │───▶│  Azure OpenAI       │
                         │  • Insights      │    │  • Filter generation  │    │  GPT-4o             │
                         │                  │    │                       │    │  Extract Knowledge / │
                         └──────────────────┘    └───────────┬───────────┘    │  Keywords /         │
                                                             │               │  Summarization      │
                                          ┌──────────────────┼──────────────────┐─────────────────────┘
                                          │                  │                  │
                                          ▼                  ▼                  ▼
                                 ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐
                                 │ Blob Storage │   │  Azure SQL  │   │   Cosmos DB     │
                                 │ Save Result  │   │ Save Docs,  │   │ Save Processing │
                                 │ Documents    │   │  Enrichment │   │ Results / Chat  │
                                 │              │   │  Cache      │   │ History         │
                                 └─────────────┘   └─────────────┘   └─────────────────┘
```

### How to Customize

If you'd like to customize the solution accelerator, here are some common areas to start:

- **Filters**: AI-generated filter dimensions are inferred from content — modify the GPT-4o prompt in `document_intelligence/service.py` to change extraction behavior
- **Insights report**: Customize the intelligence report structure in `processing/service.py`
- **BYOI (Bring Your Own Index)**: Connect any existing Azure AI Search index without uploading files
- **Chat behavior**: Modify RAG prompts and retrieval in `rag/service.py`

### Key Features

<details>
<summary>Click to learn more about the key features this solution enables</summary>

- **Ingest and extract real-world entities** — Process and extract information unique to your ingested data such as people, products, events, places, or behaviors. Used to populate dynamic filters.

- **Chat-based insights discovery** — Choose to chat with all indexed assets, a single asset, or a filtered set of assets. Active filters automatically scope the chat search context.

- **Text and document data analysis** — Analyze, compare, and synthesize materials into deep insights, making content accessible through natural language prompting.

- **Structured intelligence reports** — Auto-generate structured reports with metrics, key insights, trends, entities, risks, and opportunities. Scoped per document or across all data.

- **Multi-modal information processing** — Ingest and extract knowledge from multiple content types: PDF, DOCX, images, JSON, CSV, TXT. Supports scanned images, handwritten forms, and text-based tables via Azure Content Understanding.

- **Dynamic filter generation** — GPT-4o infers filter dimensions from content (not hardcoded). Filters persist in Azure SQL and scope chat queries.

- **Enrichment caching** — SHA-256 content hashing prevents repeated GPT-4o calls on re-upload of the same document.

- **Bring Your Own Index** — Connect an existing Azure AI Search index and immediately chat with it and generate insights — no upload needed.

</details>

---

## Quick Deploy

### How to Install or Deploy

#### Prerequisites

- Python 3.13+
- Node.js 18+
- Azure subscription with the services listed below
- ODBC Driver 18 for SQL Server (for Azure SQL)

#### Environment Variables

Create a `.env` file in the project root:

```env
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_INDEX_NAME=knowledge-mining-index

# Azure Content Understanding
AZURE_CONTENT_UNDERSTANDING_ENDPOINT=https://your-cu.cognitiveservices.azure.com/

# Azure Storage
AZURE_STORAGE_ACCOUNT=yourstorageaccount

# Azure SQL
AZURE_SQL_SERVER=your-server.database.windows.net
AZURE_SQL_DATABASE=km-db

# Azure Cosmos DB (optional — for chat persistence)
AZURE_COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com:443/
AZURE_COSMOS_DATABASE=km-db

# Microsoft Entra ID
AZURE_AD_TENANT_ID=your-tenant-id
AZURE_AD_CLIENT_ID=your-client-id

# AI Foundry (optional — for agent scripts)
AZURE_AI_AGENT_ENDPOINT=https://your-foundry.services.ai.azure.com/api/projects/your-project
AZURE_AI_AGENT_MODEL=gpt-4o
AZURE_AI_SEARCH_CONNECTION_NAME=your-search-connection
```

#### Backend

```bash
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r backend/app/requirements.txt
pip install pyodbc azure-cosmos azure-ai-projects
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend

```bash
cd frontend
npm install
npm start
```

App runs at `http://localhost:3000`, API at `http://localhost:8000`.

#### Docker

```bash
docker-compose up --build
```

### Prerequisites and Costs

To deploy this solution accelerator, ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the necessary permissions to create resource groups and resources.

| Service | Purpose | Pricing |
|---------|---------|---------|
| **Azure OpenAI Service** | Chat experience/RAG, data processing for extraction and summarization | [Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/) |
| **Azure AI Search** | Processed document information stored in a vectorized search index | [Pricing](https://azure.microsoft.com/pricing/details/search/) |
| **Azure Content Understanding** | OCR and document extraction from PDF, DOCX, images | [Pricing](https://azure.microsoft.com/pricing/details/ai-document-intelligence/) |
| **Azure Blob Storage** | Storage of document files being processed | [Pricing](https://azure.microsoft.com/pricing/details/storage/blobs/) |
| **Azure SQL Database** | Documents, files, filter schemas, enrichment cache | [Pricing](https://azure.microsoft.com/pricing/details/azure-sql-database/) |
| **Azure Cosmos DB** | Chat history and insights cache storage | [Pricing](https://azure.microsoft.com/pricing/details/cosmos-db/) |

> **Important**: To avoid unnecessary costs, remember to take down your resources if they're no longer in use.

### Azure RBAC

Assign these roles to your identity (or managed identity):

| Resource | Role |
|----------|------|
| Azure OpenAI | Cognitive Services OpenAI User |
| Azure AI Search | Search Index Data Contributor |
| Azure Blob Storage | Storage Blob Data Contributor |
| Azure SQL | db_datareader + db_datawriter |
| Azure Cosmos DB | Cosmos DB Built-in Data Contributor |
| Content Understanding | Cognitive Services User |

---

## Business Use Case

In large, enterprise organizations it's difficult and time-consuming to analyze large volumes of data. This solution accelerator addresses challenges like:

- Analyzing large volumes of documents in a timely manner, limiting quick decision-making
- Inability to compare and synthesize documents, limiting contextual relevance of insights
- Inability to extract information from charts, tables, and handwritten content, leading to incomplete analysis

**The goal of this solution accelerator is to:**

- Automate document ingestion and extraction to avoid missing critical information
- Leverage AI-extracted data to make better-informed decisions
- Accelerate analysis while reducing manual effort

> **Note**: The sample data used in this repository is synthetic and generated using Azure OpenAI service. The data is intended for use as sample data only.

---

## Supporting Documentation

### Project Structure

```
backend/
├── app/main.py                        # FastAPI app, router registration
├── config.py                          # Settings from .env
├── modules/
│   ├── ingestion/                     # Upload, delete, BYOI, filter endpoints
│   ├── document_intelligence/         # CU extraction + GPT-4o enrichment (with SQL cache)
│   ├── rag/                           # Chat: AI Search → GPT-4o (+ external index)
│   ├── processing/                    # Insights report generation
│   ├── embeddings/                    # Embedding generation
│   └── security/                      # Entra ID JWT validation, RBAC
├── storage/
│   ├── sql_service.py                 # Azure SQL persistence (primary)
│   ├── cosmos_service.py              # Cosmos DB persistence (chat + cache)
│   └── document_store.py              # In-memory document store
└── scripts/
    ├── create_agent.py                # Create AI Foundry agent
    └── test_agent.py                  # Interactive agent chat CLI

frontend/
├── src/
│   ├── api/client.ts                  # Axios client with Entra ID token
│   ├── pages/
│   │   ├── Home.tsx                   # Upload / Connect / Demo launchpad
│   │   ├── Explore.tsx                # Filters + Chat + Documents (3-column)
│   │   └── Insights.tsx               # AI intelligence report
│   ├── components/
│   │   ├── Layout.tsx                 # App shell (header + sidebar)
│   │   └── ChatInterface.tsx          # Reusable chat component
│   └── context/                       # App state + user role management
```

### Security Guidelines

This solution uses [Managed Identity](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/overview) for authentication between Azure services. All connections use Azure AD token-based auth (passwordless).

To ensure best practices:
- Enable [GitHub secret scanning](https://docs.github.com/code-security/secret-scanning/about-secret-scanning) in your repository
- Consider enabling [Microsoft Defender for Cloud](https://learn.microsoft.com/azure/defender-for-cloud/)
- Use Virtual Networks for production deployments


---

## Disclaimers

This release is an artificial intelligence (AI) system that generates text in response to user queries. The system is designed to answer questions **only** from documents that have been uploaded to the platform. It does not search the web, use external data sources, or generate responses from its general training data. If the uploaded documents do not contain sufficient information to answer a question, the system will indicate that the answer is not available.

While the system is designed to ground all responses in the uploaded documents, AI-generated outputs may occasionally contain inaccuracies or misinterpretations of the source material. Users are responsible for verifying the accuracy and suitability of any content generated by the system for their intended purposes.

This release is intended as a proof of concept only, and is not a finished or polished product. It is not intended for commercial use or distribution, and is subject to change or discontinuation without notice.

---

## License

MIT License
