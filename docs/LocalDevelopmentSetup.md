# Local Development Setup

This guide describes how to run the Conversation Knowledge Mining solution locally for development. You must first deploy the Azure resources (see the [Deployment Guide](./DeploymentGuide.md)) so the local app can connect to Azure OpenAI, Azure AI Search, Azure SQL, and Storage.

## Prerequisites

- [Python 3.9+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/) and npm
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (optional, for containerized run)
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (authenticated via `az login`)
- A completed `azd up` deployment (provides the `.env` / `azd` environment values the app needs)

## Backend (FastAPI)

From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r src/api/requirements.txt
uvicorn src.api.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Interactive API docs are at `http://localhost:8000/docs`.

> **Note:** The backend uses `DefaultAzureCredential` for Azure access. Ensure you are signed in with `az login` and have the required RBAC roles on the deployed resources.

## Frontend (React + Fluent UI)

In a second terminal:

```powershell
cd src/app
npm install
$env:REACT_APP_API_BASE_URL="http://localhost:8000/api"
npm start
```

The web app runs at `http://localhost:3000` and proxies API calls to the local backend.

## Run with Docker Compose

To run both the backend and frontend in containers:

```powershell
docker-compose up --build
```

## Environment Variables

The backend reads configuration from environment variables populated by `azd`. To export the current environment values into a local `.env` file:

```powershell
azd env get-values > .env
```

Key variables include the Azure OpenAI endpoint and deployment names, Azure AI Search endpoint and index, Azure SQL connection details, and the Storage account name.

## Utility Scripts

Useful scripts for local testing (run from the repository root):

```powershell
# Start the backend locally with environment wired up
./infra/scripts/utilities/start-local-backend.ps1

# Test the deployed agent
python ./infra/scripts/utilities/test_agent.py

# Run all feature tests
python ./infra/scripts/utilities/test_all_features.py
```

## Next Steps

Return to the [Deployment Guide](./DeploymentGuide.md) or explore [Sample Questions](./SampleQuestions.md).
