# Knowledge Mining Solution Accelerator

Ingest, extract, and analyze content from large volumes of data to gain deeper insights. Using Azure OpenAI Service, Azure AI Search, and Azure AI Foundry, this solution processes unstructured data and enables interactive exploration through natural language chat.

<div align="center">

[**SOLUTION OVERVIEW**](#solution-overview)  |  [**QUICK DEPLOY**](#quick-deploy)  |  [**BUSINESS USE CASE**](#business-use-case)  |  [**SUPPORTING DOCUMENTATION**](#supporting-documentation)

</div>

> **Note:** With any AI solutions you create using these templates, you are responsible for assessing all associated risks and for complying with all applicable laws and safety standards.

---

## Solution Overview

This solution leverages Azure OpenAI, Azure Content Understanding, Azure AI Search, and Azure AI Foundry to extract information from documents and provide insights through a chat-based interface — supporting text documents, PDFs, images, handwritten text, charts, graphs, tables, and form fields.

### Solution Architecture

```
┌──────────┐         ┌──────────────────┐         ┌───────────────────┐
│  Client  │  HTTP   │  Frontend        │  HTTP   │  Backend          │
│ (Browser)│────────▶│  React / Node    │────────▶│  FastAPI / Python │
└──────────┘         └──────────────────┘         └─────────┬─────────┘
                                                            │
                     ┌──────────────────────────────────────┼──────────────────┐
                     │                                      │                  │
                     ▼                                      ▼                  ▼
            ┌─────────────────┐                    ┌─────────────┐   ┌─────────────────┐
            │  Azure OpenAI   │                    │  Azure AI   │   │  Azure Content   │
            │  GPT-4o         │                    │  Search     │   │  Understanding   │
            └─────────────────┘                    └─────────────┘   └─────────────────┘
                     │                                      │                  │
                     ▼                                      ▼                  ▼
            ┌─────────────────┐                    ┌─────────────┐   ┌─────────────────┐
            │  AI Foundry     │                    │  Azure SQL  │   │  Blob Storage   │
            │  Agent Service  │                    │  Database   │   │                 │
            └─────────────────┘                    └─────────────┘   └─────────────────┘
```

### Key Features

<details open>
<summary>Click to learn more about the key features this solution enables</summary>

- **Chat-based insights discovery**
  Interactive chat powered by Azure AI Search and GPT-4o enables natural language exploration of your data.

- **Multi-modal information processing**
  Ingest and extract knowledge from multiple content types: PDF, DOCX, images, JSON, CSV, TXT.

- **Document analysis and extraction**
  Azure Content Understanding extracts text, tables, and structure from complex documents.

- **Dynamic filter generation**
  AI-inferred filter dimensions from content — not hardcoded. Filters scope chat queries automatically.

- **Bring Your Own Index**
  Connect an existing Azure AI Search index and immediately chat with it — no upload needed.

- **AI Agent integration**
  Azure AI Foundry agents with Azure AI Search tools for grounded question-answering.

</details>

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

4. Create the AI agent:
   ```bash
   ./infra/scripts/setup-agent.ps1
   ```

5. (Optional) Load sample data:
   ```bash
   ./infra/scripts/seed-data.ps1
   ```

6. (Optional) Configure authentication:
   - Go to Azure Portal → App Service → **Authentication** → **Add identity provider** → **Microsoft**

> ⚠️ **Important:** To avoid unnecessary costs, remember to take down your app if it's no longer in use by running `azd down`.

### Local Development

**Backend:**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r src/api/requirements.txt
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend:**
```bash
cd src/app
npm install
npm start
```

**Docker:**
```bash
docker-compose up --build
```

### Prerequisites and Costs

Check the [Azure Products by Region](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/?products=all&regions=all) page and select a region where the following services are available.

| Service | Purpose | Pricing |
|---------|---------|---------|
| [Azure AI Services (OpenAI)](https://learn.microsoft.com/azure/cognitive-services/openai/overview) | Chat, summarization, entity extraction using GPT models | [Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/) |
| [Azure AI Search](https://learn.microsoft.com/azure/search/search-what-is-azure-search) | Vector-based semantic search for document retrieval | [Pricing](https://azure.microsoft.com/pricing/details/search/) |
| [Azure App Service](https://learn.microsoft.com/azure/app-service/overview) | Hosts backend API and frontend web application | [Pricing](https://azure.microsoft.com/pricing/details/app-service/linux/) |
| [Azure Storage Account](https://learn.microsoft.com/azure/storage/common/storage-account-overview) | Stores uploaded documents and processing assets | [Pricing](https://azure.microsoft.com/pricing/details/storage/blobs/) |
| [Azure SQL Database](https://learn.microsoft.com/azure/azure-sql/database/sql-database-paas-overview) | Structured data, metadata, and enrichment cache | [Pricing](https://azure.microsoft.com/pricing/details/azure-sql-database/single/) |
| [Azure Cosmos DB](https://learn.microsoft.com/azure/cosmos-db/introduction) | Chat history storage (optional) | [Pricing](https://azure.microsoft.com/pricing/details/cosmos-db/autoscale-provisioned/) |

---

## Business Use Case

In large organizations, it's difficult and time-consuming to analyze large volumes of unstructured data. Traditional tools limit interaction with data, making it hard to surface patterns or ask follow-up questions without extensive manual exploration.

This solution addresses those challenges by enabling:

- **Natural language interaction** — Ask questions about your documents using conversational chat
- **Automated extraction** — AI extracts entities, relationships, and key information from unstructured content
- **Interactive exploration** — Dynamic filters and structured insights help users navigate large datasets
- **Faster decision-making** — Summarized, contextualized data reduces manual analysis effort

> ⚠️ The sample data used in this repository is synthetic and generated using Azure OpenAI service. The data is intended for use as sample data only.

---

## Supporting Documentation

### Project Structure

```
infra/                              # Azure Bicep infrastructure
├── main.bicep                      # Main deployment template
├── main.parameters.json            # Parameter defaults
├── modules/                        # Reusable Bicep modules
└── scripts/                        # Deployment & setup scripts
    ├── setup-agent.ps1             # Create AI Foundry agents
    ├── seed-data.ps1               # Load sample data
    ├── deploy.ps1                  # Deployment helper
    └── teardown.ps1                # Resource cleanup

src/api/
├── main.py                         # FastAPI application
├── config.py                       # Settings from .env
├── modules/
│   ├── ingestion/                  # Document upload and indexing
│   ├── document_intelligence/      # Content Understanding extraction
│   ├── rag/                        # Chat: AI Search → GPT-4o
│   ├── processing/                 # Insights report generation
│   ├── embeddings/                 # Embedding generation
│   └── security/                   # Entra ID authentication
└── storage/                        # SQL, Cosmos DB, blob persistence

src/app/
├── src/
│   ├── pages/                      # Home, Explore, Insights pages
│   ├── components/                 # Reusable UI components
│   └── api/                        # Backend API client
```

### Security Guidelines

This solution uses [Managed Identity](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/overview) for secure access to Azure resources, eliminating the need for hard-coded credentials.

To maintain strong security practices:
- Enable [GitHub secret scanning](https://docs.github.com/code-security/secret-scanning/about-secret-scanning) in your repository
- Consider enabling [Microsoft Defender for Cloud](https://learn.microsoft.com/azure/defender-for-cloud/) to monitor Azure resources
- Use [Virtual Networks](https://learn.microsoft.com/azure/app-service/overview-vnet-integration) for production deployments

---

## Provide Feedback

Have questions, find a bug, or want to request a feature? [Submit a new issue](../../issues) on this repo.

---

## Responsible AI Transparency FAQ

Please refer to [Transparency FAQ](./TRANSPARENCY_FAQ.md) for responsible AI transparency details of this solution accelerator.

---

## Disclaimers

This release is an artificial intelligence (AI) system that generates text in response to user queries. The system is designed to answer questions **only** from documents that have been uploaded to the platform. It does not search the web, use external data sources, or generate responses from its general training data.

While the system is designed to ground all responses in the uploaded documents, AI-generated outputs may occasionally contain inaccuracies. Users are responsible for verifying the accuracy and suitability of any content generated by the system.

To the extent that the Software includes components or code used in or derived from Microsoft products or services, you must also comply with the Product Terms applicable to such Microsoft Products and Services.

You must also comply with all domestic and international export laws and regulations that apply to the Software. For further information on export restrictions, visit https://aka.ms/exporting.

BY ACCESSING OR USING THE SOFTWARE, YOU ACKNOWLEDGE THAT THE SOFTWARE IS NOT DESIGNED OR INTENDED TO SUPPORT ANY USE IN WHICH A SERVICE INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE COULD RESULT IN THE DEATH OR SERIOUS BODILY INJURY OF ANY PERSON OR IN PHYSICAL OR ENVIRONMENTAL DAMAGE (COLLECTIVELY, "HIGH-RISK USE"), AND THAT YOU WILL ENSURE THAT, IN THE EVENT OF ANY INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE, THE SAFETY OF PEOPLE, PROPERTY, AND THE ENVIRONMENT ARE NOT REDUCED BELOW A LEVEL THAT IS REASONABLY, APPROPRIATE, AND LEGAL, WHETHER IN GENERAL OR IN A SPECIFIC INDUSTRY.
