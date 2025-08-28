# Local Debugging Setup

Follow the steps below to set up and run the **Conversation Knowledge Mining Solution Accelerator** locally.



## Prerequisites

Install these tools before you start:
- [Visual Studio Code](https://code.visualstudio.com/) with the following extensions:
  - [Azure Tools](https://marketplace.visualstudio.com/items?itemName=ms-vscode.vscode-node-azure-pack)
  - [Bicep](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-bicep)
  - [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
- [Python 3.11](https://www.python.org/downloads/). **Important:** Check "Add Python to PATH" during installation.
- [PowerShell 7.0+](https://github.com/PowerShell/PowerShell#get-powershell).
- [Node.js (LTS)](https://nodejs.org/en).
- [Git](https://git-scm.com/downloads).
- [Azure Developer CLI (azd) v1.15.0+](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd).
- [Microsoft ODBC Driver 17](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver16) for SQL Server.


## Setup Steps

### Clone the Repository

Choose a location on your local machine where you want to store the project files. We recommend creating a dedicated folder for your development projects.

#### Using Command Line/Terminal

1. **Open your terminal or command prompt. Navigate to your desired directory and Clone the repository:**
   ```bash
   git clone https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator.git
   ```

2. **Navigate to the project directory:**
   ```bash
   cd Conversation-Knowledge-Mining-Solution-Accelerator
   ```

3. **Open the project in Visual Studio Code:**
   ```bash
   code .
   ```

## Local Debugging

To customize the accelerator or run it locally, you have two options:

### Option 1: Use Existing Environment

If you already have an Azure environment deployed with the necessary resources, ensure you have the required `.env` files with all the necessary environment variables in the appropriate locations:
- **Backend API environment variables**: `src/api/.env` - You can get these from:
  - `.azure/<environment-name>/` folder if deployed using `azd up`
  - Azure Portal App Service environment variables if deployed using custom deployment methods
- **Frontend environment variables**: `src/App/.env`

> **Note**: For a complete list of required environment variables and any value changes needed for local debugging, refer to the [Environment Variables](#environment-variables) section below.

### Option 2: Deploy New Environment

If you don't have an existing environment, you must first deploy the Azure resources. Follow the complete deployment instructions in the [Local Environment section of the Deployment Guide](https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/blob/main/documents/DeploymentGuide.md#local-environment). This will generate a `.env` file located in the `.azure` folder with all the necessary environment variables.

> **Important**: Regardless of which option you choose, ensure all required environment variables are properly configured before proceeding with local development. Refer to the [Environment Variables](#environment-variables) section below.

## Environment Variables

### Backend API Environment Variables (`src/api/.env`):

| App Setting | Value | Note |
|-------------|-------|------|
| `SOLUTION_NAME` |  | Prefix used to uniquely identify resources in the deployment |
| `RESOURCE_GROUP_NAME` |  | Name of the Azure Resource Group |
| `APP_ENV` | `dev` | Set APP_ENV in your .env file to control Azure authentication. Set the environment variable to dev to use Azure CLI credentials, or to prod to use Managed Identity for production. Ensure you're logged in via az login when using dev in local. |
| `APPINSIGHTS_INSTRUMENTATIONKEY` |  | Instrumentation Key for Azure Application Insights |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` |  | Connection string for Application Insights |
| `AZURE_AI_PROJECT_CONN_STRING` |  | Connection string for the Azure AI project |
| `AZURE_AI_AGENT_API_VERSION` |  | API version for the Azure AI Agent |
| `AZURE_AI_PROJECT_NAME` |  | Name of the Azure AI project |
| `AZURE_AI_SEARCH_ENDPOINT` |  | Endpoint URL for Azure Cognitive Search |
| `AZURE_AI_SEARCH_INDEX` | `call_transcripts_index` | Name of the Azure AI Search index |
| `AZURE_AI_SEARCH_CONNECTION_NAME` |  | Connection name for Azure AI Search |
| `AZURE_AI_FOUNDRY_NAME` |  | Name of the Azure AI Foundry resource |
| `AZURE_AI_SEARCH_NAME` |  | Name of the Azure AI Search service |
| `AZURE_EXISTING_AI_PROJECT_RESOURCE_ID` |  | Resource ID of existing AI project (if using existing foundry project) |
| `AZURE_COSMOSDB_ACCOUNT` |  | Name of the Azure Cosmos DB account |
| `AZURE_COSMOSDB_CONVERSATIONS_CONTAINER` | `conversations` | Name of the Cosmos DB container for conversation data |
| `AZURE_COSMOSDB_DATABASE` | `db_conversation_history` | Name of the Cosmos DB database |
| `AZURE_OPENAI_DEPLOYMENT_MODEL` |  | Name of the OpenAI model deployment |
| `AZURE_OPENAI_ENDPOINT` |  | Endpoint for the Azure OpenAI resource |
| `AZURE_OPENAI_MODEL_DEPLOYMENT_TYPE` |  | Deployment type for OpenAI model |
| `AZURE_OPENAI_EMBEDDING_MODEL` |  | Name of the embedding model used for vector search |
| `AZURE_OPENAI_API_VERSION` |  | API version for Azure OpenAI |
| `AZURE_OPENAI_RESOURCE` |  | Name of the Azure OpenAI resource |
| `REACT_APP_LAYOUT_CONFIG` |  | Layout configuration used by the React frontend |
| `SQLDB_DATABASE` |  | Name of the Azure SQL Database |
| `SQLDB_SERVER` |  | Name of the Azure SQL Server |
| `AZURE_AI_AGENT_ENDPOINT` |  | Endpoint for the Azure AI Agent |
| `AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME` |  | Deployment name for the AI agent model |

### Frontend App Environment Variables (`src/App/.env`):

| App Setting | Value | Note |
|-------------|-------|------|
| `REACT_APP_API_BASE_URL` | `http://127.0.0.1:8000` | Frontend API base URL for local development |

## Running with Automated Script

For convenience, you can use the provided startup scripts that handle environment setup and start both services:

**Windows:**
```cmd
cd src
.\start.cmd
```

**macOS/Linux:**
```bash
cd src
chmod +x start.sh
./start.sh
```

### What the Scripts Do

The startup scripts automate the complete local development setup:

- **Environment & Authentication**: Copies `.env` files from Azure deployment and handles Azure login
- **Role Assignments**: Assigns required Azure permissions (SQL, Cosmos DB, Search, AI services)
- **Dependencies**: Creates virtual environment and installs Python/npm packages
- **Service Launch**: Starts both backend (port 8000) and frontend (port 3000) servers

> **Note**: The script includes a 30-second wait time for the backend to initialize before starting the frontend. However, sometimes it might take more time. If you see connection errors in the frontend initially, please wait a moment for the backend to become fully ready, then reload the frontend once the backend is available.

## Running Backend and Frontend Separately

### Manually Assign Roles

To run the accelerator locally when the solution is secured by RBAC, you need to assign roles to your principal ID. You can get your principal ID from Microsoft Entra ID.

**Assign the following roles to your `PRINCIPALID` (via Azure Portal or Azure CLI):**

| Role | GUID | Azure Service |
|------|------|---------------|
| Azure AI User | `53ca6127-db72-4b80-b1b0-d745d6d5456d` | AI Foundry |
| Cognitive Services OpenAI User | `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` | AI Foundry Project |
| Key Vault Secrets User | `4633458b-17de-408a-b874-0445c86b69e6` | Azure Key Vault |
| Search Index Data Contributor | `8ebe5a00-799e-43f5-93ac-243d3dce84a7` | Azure AI Search |
| Search Index Data Reader | `1407120a-92aa-4202-b7e9-c0e197c71c8f` | Azure AI Search |
| Search Service Contributor | `7ca78c08-252a-4471-8644-bb5ff32d4ba0` | Azure AI Search |
| Storage Blob Data Contributor | `ba92f5b4-2d11-453d-a403-e96b0029c9fe` | Azure Storage Account |

**Assign Cosmos DB Built-in Data Contributor role (via Azure CLI only):**

```bash
# Get your principal ID (if you don't know it)
az ad signed-in-user show --query id -o tsv

# Assign Cosmos DB Built-in Data Contributor role
az cosmosdb sql role assignment create \
  --account-name <YOUR_COSMOS_ACCOUNT_NAME> \
  --resource-group <YOUR_RESOURCE_GROUP> \
  --scope "/" \
  --principal-id <YOUR_PRINCIPAL_ID> \
  --role-definition-id "00000000-0000-0000-0000-000000000002"
```

#### Setup Azure SQL Database Access

##### Option 1: Set Yourself as SQL Server Admin (for single user scenarios)

1. Go to your SQL Server resource in Azure Portal
2. Under **"Security"**, click **"Microsoft Entra ID"**
3. Click **"Set admin"** and search for your user account
4. Select your user and click **"Save"**

##### Option 2: Create Database User with Specific Roles (recommended)

1. First, ensure you have admin access to the SQL Server (Option 1 above)
2. Connect to your Azure SQL Database using SQL Server Management Studio or the Query Editor in Azure Portal
3. Run the following SQL script (replace the username with your actual Microsoft Entra ID account):

```sql
DECLARE @username NVARCHAR(MAX) = N'your-email@yourdomain.com';
DECLARE @cmd NVARCHAR(MAX);

-- Create the external user if it does not exist
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = @username)
BEGIN
    SET @cmd = N'CREATE USER ' + QUOTENAME(@username) + ' FROM EXTERNAL PROVIDER';
    EXEC(@cmd);
END

-- Add user to db_datareader if not already a member
IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members drm
    JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
    JOIN sys.database_principals u ON drm.member_principal_id = u.principal_id
    WHERE r.name = 'db_datareader' AND u.name = @username
)
BEGIN
    EXEC sp_addrolemember N'db_datareader', @username;
END

-- Add user to db_datawriter if not already a member
IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members drm
    JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
    JOIN sys.database_principals u ON drm.member_principal_id = u.principal_id
    WHERE r.name = 'db_datawriter' AND u.name = @username
)
BEGIN
    EXEC sp_addrolemember N'db_datawriter', @username;
END

-- Verify the user roles
SELECT u.name AS [UserName], r.name AS [RoleName]
FROM sys.database_role_members drm
INNER JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
INNER JOIN sys.database_principals u ON drm.member_principal_id = u.principal_id
WHERE u.name = @username;
```

### Develop & Run the Backend API

#### Step 1: Create Virtual Environment (Recommended)

Open your terminal and navigate to the root folder of the project, then create the virtual environment:

```bash
# Navigate to the project root folder
cd Conversation-Knowledge-Mining-Solution-Accelerator

# Create virtual environment in the root folder
python -m venv .venv

# Activate virtual environment (Windows)
.venv\Scripts\activate

# Activate virtual environment (macOS/Linux)
source .venv/bin/activate
```

> **Note**: After activation, you should see `(.venv)` in your terminal prompt indicating the virtual environment is active.

#### Step 2: Install Dependencies and Run

To develop and run the backend API locally:

```bash
# Navigate to the API folder (while virtual environment is activated)
cd src/api

# Upgrade pip
python -m pip install --upgrade pip

# Install Python dependencies
pip install -r requirements.txt

# Run the backend API
python app.py
```

The backend API will run on `http://127.0.0.1:8000` by default.

> **Note**: Make sure your virtual environment is activated before running these commands. You should see `(.venv)` in your terminal prompt when the virtual environment is active.

### Develop & Run the Frontend Locally

To run the React frontend in development mode:

```bash
cd src/App
npm install
npm start
```

The frontend will run on `http://localhost:3000` and automatically proxy API requests to the backend.

## Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://127.0.0.1:8000
