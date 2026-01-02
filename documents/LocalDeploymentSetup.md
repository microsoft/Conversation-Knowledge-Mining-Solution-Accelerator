# Local Development Setup Guide

This guide provides comprehensive instructions for setting up the **Conversation Knowledge Mining Solution Accelerator** for local development across Windows and Linux platforms.

## Important Setup Notes

### Multi-Service Architecture

This application consists of two separate services that run independently:

1. **Backend API** - Python FastAPI server providing REST endpoints
2. **Frontend** - React-based user interface

> ⚠️ **Critical**: Each service must run in its own terminal/console window
>
> • Do NOT close terminals while services are running  
> • Open 2 separate terminal windows for local development  
> • Each service will occupy its terminal and show live logs

**Terminal Organization:**

• **Terminal 1**: Backend API - HTTP server on port 8000  
• **Terminal 2**: Frontend - Development server on port 3000

---

### Path Conventions

All paths in this guide are relative to the repository root directory:

```
Conversation-Knowledge-Mining-Solution-Accelerator/    ← Repository root (start here)
├── src/
│   ├── api/                                           
│   │   ├── app.py                          ← Backend API entry point
│   │   └── .env                            ← Backend config file
│   └── App/                                           
│       ├── package.json                    ← Frontend entry point
│       └── .env                            ← Frontend config file
├── infra/                                  ← Infrastructure as Code (Bicep)
└── documents/                              ← Documentation (you are here)
```

Before starting any step, ensure you are in the repository root directory:

```powershell
# Verify you're in the correct location
Get-Location  # Windows PowerShell - should show: ...\Conversation-Knowledge-Mining-Solution-Accelerator
pwd           # Linux/macOS - should show: .../Conversation-Knowledge-Mining-Solution-Accelerator

# If not, navigate to repository root
cd path\to\Conversation-Knowledge-Mining-Solution-Accelerator
```

---

### Configuration Files

This project uses separate `.env` files in each service directory with different configuration requirements:

• **Backend API**: `src/api/.env` - Azure service endpoints, credentials, and API configuration  
• **Frontend**: `src/App/.env` - API base URL and React app settings

When copying `.env` samples, always navigate to the specific service directory first.

---

## Step 1: Prerequisites - Install Required Tools

### Windows Development

#### Option 1: Native Windows (PowerShell)

```powershell
# Install Python 3.11 and Git
winget install Python.Python.3.11
winget install Git.Git

# Install Node.js for frontend
winget install OpenJS.NodeJS.LTS

# Install Azure CLI (required for authentication)
winget install Microsoft.AzureCLI

# Install Azure Developer CLI (azd)
winget install Microsoft.Azd

# Install Microsoft ODBC Driver 17 for SQL Server
# Download from: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
```

**Note**: After installation, restart your terminal or open a new PowerShell window to refresh environment variables.

#### Option 2: Windows with WSL2 (Recommended)

```powershell
# Install WSL2 first (run in PowerShell as Administrator):
wsl --install -d Ubuntu

# Then in WSL2 Ubuntu terminal:
sudo apt update && sudo apt install python3.11 python3.11-venv git curl nodejs npm -y

# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Install ODBC Driver for SQL Server on WSL2
curl https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sed 's#^deb #deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] #' | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
```

---

### Linux Development

#### Ubuntu/Debian

```bash
# Install prerequisites
sudo apt update && sudo apt install python3.11 python3.11-venv git curl nodejs npm -y

# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Install ODBC Driver for SQL Server
# Add Microsoft GPG key (modern keyring-based approach, avoiding deprecated apt-key)
sudo mkdir -p /etc/apt/keyrings
curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor | sudo tee /etc/apt/keyrings/microsoft-prod.gpg > /dev/null

# Add Microsoft package repository using the keyring with signed-by
UBUNTU_VERSION=$(lsb_release -rs)
UBUNTU_CODENAME=$(lsb_release -cs)
ARCHITECTURE=$(dpkg --print-architecture)
echo "deb [arch=${ARCHITECTURE} signed-by=/etc/apt/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/ubuntu/${UBUNTU_VERSION}/prod ${UBUNTU_CODENAME} main" | sudo tee /etc/apt/sources.list.d/mssql-release.list

sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
```

#### RHEL/CentOS/Fedora

```bash
# Install prerequisites
sudo dnf install python3.11 python3.11-devel git curl gcc nodejs npm -y

# Install Azure CLI
sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
sudo dnf install -y https://packages.microsoft.com/config/rhel/$(rpm -E %{rhel})/packages-microsoft-prod.rpm
sudo dnf install azure-cli -y

# Install ODBC Driver for SQL Server
curl https://packages.microsoft.com/config/rhel/$(rpm -E %{rhel})/prod.repo | sudo tee /etc/yum.repos.d/mssql-release.repo
sudo ACCEPT_EULA=Y dnf install -y msodbcsql17
```

---

### Clone the Repository

```bash
git clone https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator.git
cd Conversation-Knowledge-Mining-Solution-Accelerator
```

---

### Configure Git (Required for Commits)

Before making any commits or pushes, configure your Git identity:

```bash
# Set your name (this will appear in commit history)
git config --global user.name "Your Name"

# Set your email (this will appear in commit history)
git config --global user.email "your.email@example.com"

# Verify your configuration
git config --global --list

# Optional: Set default branch name to 'main'
git config --global init.defaultBranch main

# Optional: Configure line ending handling
# Windows users:
git config --global core.autocrlf true

# Linux/macOS users:
git config --global core.autocrlf input
```

> **Note**: Use your actual name and email address. If you're contributing to the repository, use the email associated with your GitHub account.

#### Additional Git Configuration (Optional)

```bash
# Set default editor for commit messages
git config --global core.editor "code --wait"  # For VS Code
# or
git config --global core.editor "vim"  # For Vim

# Enable colored output
git config --global color.ui auto

# Set default pull behavior (recommended)
git config --global pull.rebase false  # merge (default)
# or
git config --global pull.rebase true   # rebase

# Cache credentials (Windows)
git config --global credential.helper wincred

# Cache credentials (Linux/macOS - cache for 1 hour)
git config --global credential.helper cache
git config --global credential.helper 'cache --timeout=3600'
```

#### Verify Git Configuration

```bash
# View all global Git settings
git config --global --list

# View specific settings
git config user.name
git config user.email
```

---

## Step 2: Development Tools Setup

### Visual Studio Code (Recommended)

#### Required Extensions

Create `.vscode/extensions.json` in the workspace root and copy the following JSON:

```json
{
    "recommendations": [
        "ms-python.python",
        "ms-python.pylint",
        "ms-python.black-formatter",
        "ms-python.flake8",
        "ms-vscode-remote.remote-wsl",
        "ms-azuretools.vscode-bicep",
        "ms-azuretools.vscode-azureresourcegroups",
        "redhat.vscode-yaml",
        "ms-vscode.azure-account",
        "dbaeumer.vscode-eslint",
        "esbenp.prettier-vscode"
    ]
}
```

VS Code will prompt you to install these recommended extensions when you open the workspace.

#### Settings Configuration

Create `.vscode/settings.json` and copy the following JSON:

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/src/api/.venv/bin/python",
    "python.terminal.activateEnvironment": true,
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.organizeImports": "explicit"
        }
    },
    "black-formatter.args": [
        "--line-length=100"
    ],
    "flake8.args": [
        "--max-line-length=100"
    ],
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "files.associations": {
        "*.yaml": "yaml",
        "*.yml": "yaml"
    },
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": "explicit"
    }
}
```

---

## Step 3: Azure Authentication Setup

Before configuring services, authenticate with Azure:

```bash
# Login to Azure CLI
az login

# Set your subscription
az account set --subscription "your-subscription-id"

# Verify authentication
az account show
```

### Azure Deployment Prerequisites

Before running locally, you need to have deployed the solution to Azure to get the required resources and configuration values. Follow one of these options:

#### Option A: Use Existing Deployment

If you already have deployed the solution using `azd up`, your environment variables are stored in `.azure/<environment-name>/.env`

#### Option B: Deploy New Environment

Follow the [Deployment Guide](./DeploymentGuide.md) to deploy the solution using Azure Developer CLI:

```bash
# Initialize and deploy
azd init
azd up
```

This will create all necessary Azure resources and generate environment configuration files.

---

### Required Azure RBAC Permissions

To run the application locally, your Azure account needs the following role assignments on the deployed resources:

#### Get Your Principal ID

```bash
# For Bash
PRINCIPAL_ID=$(az ad signed-in-user show --query id -o tsv)
echo $PRINCIPAL_ID

# For PowerShell
$PRINCIPAL_ID = (az ad signed-in-user show --query id -o tsv)
Write-Host $PRINCIPAL_ID
```

#### Azure AI Foundry & OpenAI Access

```bash
# Assign Azure AI User role
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Azure AI User" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.MachineLearningServices/workspaces/<ai-foundry-name>"

# Assign Cognitive Services OpenAI User role
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Cognitive Services OpenAI User" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<openai-resource-name>"
```

#### Azure AI Search Access

```bash
# Assign Search Index Data Contributor role
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Search Index Data Contributor" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Search/searchServices/<search-service-name>"

# Assign Search Index Data Reader role
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Search Index Data Reader" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Search/searchServices/<search-service-name>"

# Assign Search Service Contributor role
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Search Service Contributor" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Search/searchServices/<search-service-name>"
```

#### Cosmos DB Access

```bash
# Assign Cosmos DB Built-in Data Contributor role
az role assignment create \
  --role "Cosmos DB Built-in Data Contributor" \
  --assignee $PRINCIPAL_ID \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/<resource-group>/providers/Microsoft.DocumentDB/databaseAccounts/<cosmos-account-name>"
```

#### Azure Storage Access

```bash
# Assign Storage Blob Data Contributor role
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Storage Blob Data Contributor" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Storage/storageAccounts/<storage-account-name>"
```

> **Note**: RBAC permission changes can take 5-10 minutes to propagate. If you encounter "Forbidden" errors after assigning roles, wait a few minutes and try again.

---

### Setup Azure SQL Database Access

You need database access to read conversation transcripts and metadata. Choose one of these options:

#### Option 1: Set Yourself as SQL Server Admin (for single user scenarios)

1. Go to your SQL Server resource in Azure Portal
2. Under **"Security"**, click **"Microsoft Entra ID"**
3. Click **"Set admin"** and search for your user account
4. Select your user and click **"Save"**

#### Option 2: Create Database User with Specific Roles (recommended)

1. First, ensure you have admin access to the SQL Server (Option 1 above)
2. Connect to your Azure SQL Database using [Azure Data Studio](https://azure.microsoft.com/en-us/products/data-studio/), [SQL Server Management Studio](https://learn.microsoft.com/en-us/sql/ssms/download-sql-server-management-studio-ssms), or the Query Editor in Azure Portal
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

---

## Step 4: Backend API Setup & Run Instructions

> 📋 **Terminal Reminder**: Open a dedicated terminal window (Terminal 1) for the Backend API service. All commands in this section assume you start from the repository root directory.

The Backend API provides REST endpoints for the frontend and handles all Azure service integrations including AI Foundry agents, Cosmos DB, Azure SQL, and Azure AI Search.

### 4.1. Navigate to API Directory

```bash
# From repository root
cd src/api
```

### 4.2. Configure Backend API Environment Variables

#### Using Deployed Environment Variables

If you deployed using `azd up`, copy the environment file from the Azure deployment:

```powershell
# Windows PowerShell - copy from azd environment
Copy-Item "..\..\.azure\<environment-name>\.env" ".env"

# Linux/macOS - copy from azd environment
cp ../../.azure/<environment-name>/.env .env
```

#### Manual Configuration

If you need to create the `.env` file manually, you can use the `.env.sample` file as a template:

```bash
# Copy from sample file
cp .env.sample .env  # Linux/macOS
# or
Copy-Item .env.sample .env  # Windows PowerShell

# Or create new file
touch .env  # Linux/macOS
# or
New-Item .env  # Windows PowerShell
```

Add the following environment variables to `src/api/.env`:

```bash
# Solution Configuration
SOLUTION_NAME=<your-solution-prefix>
RESOURCE_GROUP_NAME=<your-resource-group>
APP_ENV=dev  # Use 'dev' for local development with Azure CLI auth, 'prod' for Managed Identity

# Application Insights
APPINSIGHTS_INSTRUMENTATIONKEY=<instrumentation-key>
APPLICATIONINSIGHTS_CONNECTION_STRING=<connection-string>

# Azure AI Foundry Configuration
AZURE_AI_PROJECT_CONN_STRING=<ai-project-connection-string>
AZURE_AI_AGENT_API_VERSION=2024-11-01-preview
AZURE_AI_PROJECT_NAME=<ai-project-name>
AZURE_AI_FOUNDRY_NAME=<ai-foundry-resource-name>
AZURE_EXISTING_AI_PROJECT_RESOURCE_ID=<ai-project-resource-id>
AZURE_AI_AGENT_ENDPOINT=<ai-agent-endpoint>
AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME=<agent-model-deployment>

# Azure AI Search Configuration
AZURE_AI_SEARCH_ENDPOINT=<search-endpoint>
AZURE_AI_SEARCH_INDEX=call_transcripts_index
AZURE_AI_SEARCH_CONNECTION_NAME=<search-connection-name>
AZURE_AI_SEARCH_NAME=<search-service-name>

# Azure OpenAI Configuration
AZURE_OPENAI_DEPLOYMENT_MODEL=<model-deployment-name>
AZURE_OPENAI_ENDPOINT=<openai-endpoint>
AZURE_OPENAI_MODEL_DEPLOYMENT_TYPE=<deployment-type>
AZURE_OPENAI_EMBEDDING_MODEL=<embedding-model-name>
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_RESOURCE=<openai-resource-name>

# Cosmos DB Configuration
AZURE_COSMOSDB_ACCOUNT=<cosmos-account-name>
AZURE_COSMOSDB_CONVERSATIONS_CONTAINER=conversations
AZURE_COSMOSDB_DATABASE=db_conversation_history

# Azure SQL Database Configuration
SQLDB_DATABASE=<sql-database-name>
SQLDB_SERVER=<sql-server-name>.database.windows.net

# Feature Flags
USE_CHAT_HISTORY_ENABLED=True
DISPLAY_CHART_DEFAULT=False
AZURE_COSMOSDB_ENABLE_FEEDBACK=True

# Logging Configuration (Optional)
AZURE_BASIC_LOGGING_LEVEL=INFO
AZURE_PACKAGE_LOGGING_LEVEL=WARNING
AZURE_LOGGING_PACKAGES=

# Frontend Layout Configuration
REACT_APP_LAYOUT_CONFIG=<layout-config-json>
```

> ⚠️ **Important**: 
> - Set `APP_ENV=dev` for local development. This enables Azure CLI authentication.
> - Ensure you're logged in via `az login` before running the backend.
> - Set `APP_ENV=prod` only when deploying to Azure App Service with Managed Identity.

### 4.3. Install Backend API Dependencies

```bash
# Ensure you're in the src/api directory
cd src/api

# Create and activate virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

> ⚠️ **Important**: Always activate the virtual environment before installing dependencies or running the API. You should see `(.venv)` in your terminal prompt when activated.

#### Troubleshooting Installation Issues

**Windows PowerShell Execution Policy Error:**
```powershell
# If you get "cannot be loaded because running scripts is disabled"
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Python Version Issues:**
```bash
# Verify Python version
python --version  # Should be Python 3.11+

# If multiple Python versions installed, use specific version
python3.11 -m venv .venv
```

### 4.4. Run the Backend API

```bash
# Make sure you're in the src/api directory with virtual environment activated
cd src/api

# Run the FastAPI application
python app.py
```

The Backend API will start at:

• **API Base**: `http://127.0.0.1:8000`  
• **API Documentation (Swagger)**: `http://127.0.0.1:8000/docs`  
• **Alternative API Docs (ReDoc)**: `http://127.0.0.1:8000/redoc`

#### Expected Output

When successfully running, you should see output similar to:

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

#### Common Backend Issues

**Port Already in Use:**
```bash
# Find process using port 8000
# Windows:
netstat -ano | findstr :8000
taskkill /PID <process-id> /F

# Linux/macOS:
lsof -i :8000
kill -9 <process-id>
```

**Module Not Found Errors:**
```bash
# Ensure virtual environment is activated
# Windows: You should see (.venv) in prompt
# Then reinstall dependencies
pip install -r requirements.txt
```

**Azure Authentication Errors:**
```bash
# Ensure you're logged in
az login
az account show

# Verify APP_ENV is set to 'dev' in .env file
```

---

## Step 5: Frontend (UI) Setup & Run Instructions

> 📋 **Terminal Reminder**: Open a second dedicated terminal window (Terminal 2) for the Frontend. Keep Terminal 1 (Backend API) running. All commands assume you start from the repository root directory.

The Frontend is a React-based web application that provides an interactive interface for exploring conversational insights through natural language queries.

### 5.1. Navigate to Frontend Directory

```bash
# From repository root
cd src/App
```

### 5.2. Configure Frontend Environment Variables

Create a `.env` file in the `src/App` directory:

```bash
# Create .env file
touch .env  # Linux/macOS
# or
New-Item .env  # Windows PowerShell
```

Add the following to `src/App/.env`:

```bash
# API Configuration
REACT_APP_API_BASE_URL=http://127.0.0.1:8000

# Optional: Enable debug logging
REACT_APP_DEBUG=true
```

> ⚠️ **Important**: 
> - The `REACT_APP_API_BASE_URL` must match the backend API address (default: `http://127.0.0.1:8000`)
> - React apps require `REACT_APP_` prefix for custom environment variables
> - After changing `.env`, restart the frontend development server

### 5.3. Install UI Dependencies

```bash
# Make sure you're in the src/App directory
cd src/App

# Install npm packages
npm install
```

This will install all dependencies listed in `package.json`, including:
- React and React DOM
- Fluent UI components (@fluentui/react, @fluentui/react-components)
- Azure MSAL for authentication (@azure/msal-react, @azure/msal-browser)
- Chart.js and D3 for data visualization
- Axios for API calls
- Development tools and testing libraries

> **Note**: The `package.json` includes a proxy configuration. If you see `"proxy": "http://localhost:5000"` in package.json but your backend runs on port 8000, you may need to update it:
> ```json
> "proxy": "http://localhost:8000"
> ```
> Or rely on the `REACT_APP_API_BASE_URL` environment variable instead.

#### Troubleshooting npm Installation

**npm Not Found:**
```bash
# Verify Node.js installation
node --version
npm --version

# If not installed, install Node.js LTS from https://nodejs.org/
```

**Permission Errors (Linux/macOS):**
```bash
# Do NOT use sudo with npm install
# If you have permission issues, fix npm permissions:
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

**Dependency Conflicts:**
```bash
# Clear npm cache and reinstall
rm -rf node_modules package-lock.json  # Linux/macOS
# or
Remove-Item -Recurse node_modules, package-lock.json  # Windows PowerShell

npm cache clean --force
npm install
```

### 5.4. Build the UI (Optional)

For production builds:

```bash
npm run build
```

This creates an optimized production build in the `build/` directory. This step is optional for local development.

### 5.5. Start Development Server

```bash
# Start the React development server
npm start
```

The app will start at:

```
http://localhost:3000
```

The browser should automatically open. If not, manually navigate to `http://localhost:3000`

#### Expected Output

When successfully running, you should see output similar to:

```
Compiled successfully!

You can now view the app in the browser.

  Local:            http://localhost:3000
  On Your Network:  http://192.168.1.x:3000

Note that the development build is not optimized.
To create a production build, use npm run build.

webpack compiled successfully
```

#### React Development Features

The development server provides:
- **Hot Module Replacement (HMR)**: Automatically refreshes when you save changes
- **Error Overlay**: Shows compilation errors and runtime errors in the browser
- **API Proxy**: Uses `REACT_APP_API_BASE_URL` from `.env` to connect to backend at `http://127.0.0.1:8000`
- **Azure AD Authentication**: Integrated with @azure/msal-react for user authentication

#### Common Frontend Issues

**Port 3000 Already in Use:**
```bash
# Option 1: Use a different port
PORT=3001 npm start  # Linux/macOS
$env:PORT=3001; npm start  # Windows PowerShell

# Option 2: Kill process on port 3000
# Windows:
netstat -ano | findstr :3000
taskkill /PID <process-id> /F

# Linux/macOS:
lsof -i :3000
kill -9 <process-id>
```

**Cannot Connect to Backend API:**
```bash
# 1. Verify backend is running on http://127.0.0.1:8000
# 2. Check REACT_APP_API_BASE_URL in src/App/.env
# 3. Check browser console for CORS errors
# 4. Restart frontend after changing .env: Ctrl+C then npm start
```

**Module Not Found or TypeScript Errors:**
```bash
# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

---

## Step 6: Verify All Services Are Running

Before using the application, confirm both services are running in separate terminals:

### Terminal Status Checklist

| Terminal | Service | Command | Expected Log Message | Access URL |
|----------|---------|---------|----------------------|------------|
| Terminal 1 | Backend API | `python app.py` | `Uvicorn running on http://127.0.0.1:8000` | http://127.0.0.1:8000 |
| Terminal 2 | Frontend | `npm start` | `webpack compiled successfully` | http://localhost:3000 |

### Quick Verification

#### 1. Check Backend API Health

Open a new terminal (Terminal 3) and test the API:

```bash
# Test API endpoint
curl http://127.0.0.1:8000/health

# Expected response: {"status":"healthy"} or similar 

```

#### 2. Check Frontend

• Open browser to `http://localhost:3000`  
• Should see the Conversation Knowledge Mining UI  
• Check browser console (F12) for any errors  
• Verify no "Cannot connect to backend" errors

#### 3. Test End-to-End Connection

1. Navigate to the main application interface at `http://localhost:3000`
2. Try entering a sample query in the chat interface
3. Verify the frontend successfully communicates with the backend
4. Check Terminal 1 (Backend) for incoming API request logs

### Common Issues

**Service not starting?**

• Ensure you're in the correct directory  
• Verify virtual environment is activated (Python services)  
• Check that port is not already in use (8000 for API, 3000 for frontend)  
• Review error messages in the terminal  
• Verify all environment variables are set in `.env` files

**Can't access services?**

• Verify firewall isn't blocking ports 8000 or 3000  
• Try `http://localhost:port` instead of `http://127.0.0.1:port` or vice versa  
• Ensure services show "startup complete" messages  
• Check for proxy or VPN interference

**Backend connects but returns errors?**

• Verify Azure authentication: run `az account show`  
• Check RBAC permissions are assigned (Step 3)  
• Wait 5-10 minutes after assigning permissions for propagation  
• Verify `APP_ENV=dev` in `src/api/.env`

---

## Troubleshooting 

### Common Issues

#### Python Version Issues

```bash
# Check available Python versions (should be Python 3.11+)
python --version
python3 --version
python3.11 --version

# If python3.11 or newer version not found, install it:
# Windows: 
winget install Python.Python.3.11

# Ubuntu: 
sudo apt install python3.11 python3.11-venv

# Verify installation
python3.11 --version
```

#### Virtual Environment Issues

```bash
# Recreate virtual environment
# Windows:
Remove-Item -Recurse .venv
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Linux/macOS:
rm -rf .venv
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Permission Issues (Linux/macOS)

```bash
# Fix ownership of files
sudo chown -R $USER:$USER .

# Fix execution permissions for scripts
chmod +x start.sh
```

#### Windows-Specific Issues

```powershell
# PowerShell execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Long path support (Windows 10 1607+, run as Administrator)
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force

# SSL certificate issues
python -m pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org pip
```

### Environment Variable Issues

```bash
# Check environment variables are loaded
# Linux/macOS:
env | grep AZURE
env | grep REACT_APP

# Windows PowerShell:
Get-ChildItem Env:AZURE*
Get-ChildItem Env:REACT_APP*

# Validate .env file format (should show key=value pairs)
# Linux/macOS:
cat .env | grep -v '^#' | grep '='

# Windows PowerShell:
Get-Content .env | Where-Object { $_ -notmatch '^#' -and $_ -match '=' }
```

### Azure Connection Issues

```bash
# Verify Azure CLI authentication
az account show
az account list --output table

# Re-authenticate if needed
az login --use-device-code

# Test specific resource access
az cosmosdb show --name <cosmos-account> --resource-group <rg-name>
az sql db show --name <db-name> --server <server-name> --resource-group <rg-name>
```

### Database Connection Issues

#### SQL Database Connection Errors

```bash
# Common issues:
# 1. Firewall rules - Add your IP in Azure Portal
# 2. ODBC Driver not installed - See Step 1 prerequisites
# 3. Entra ID authentication not configured - See Step 3
# 4. Check backend API logs for connection errors
```

**SQL Server Firewall Configuration:**
1. Go to Azure Portal → Your SQL Server
2. Under **Security** → **Networking**
3. Add your client IP address or enable "Allow Azure services and resources to access this server"
4. Click **Save**

**Verify ODBC Driver Installation:**
```bash
# Windows PowerShell:
Get-OdbcDriver | Where-Object {$_.Name -like "*SQL Server*"}

# Linux:
odbcinst -q -d
```

#### Cosmos DB Connection Errors

```bash
# Verify Cosmos DB role assignment
az cosmosdb sql role assignment list \
  --account-name <cosmos-account> \
  --resource-group <rg-name>

# Look for your principal ID in the output
# If missing, re-run the role assignment from Step 3
```

**Common Cosmos DB Errors:**
- `403 Forbidden`: RBAC permissions not assigned or propagating (wait 5-10 minutes)
- `ResourceNotFound`: Check database/container names in .env file
- `Unauthorized`: Azure CLI not logged in or wrong subscription

### API Errors and Debugging

#### Enable Detailed Logging

Edit `src/api/.env` and add:

```bash
# Enable debug mode
DEBUG=true
LOG_LEVEL=DEBUG
AZURE_BASIC_LOGGING_LEVEL=DEBUG
```

Restart the backend API to see detailed logs.

#### Check API Logs

Watch Terminal 1 (Backend API) for error messages. Common errors:

**403 Forbidden:**
```bash
# RBAC permissions not assigned or not propagated yet
# Solution: Wait 5-10 minutes or reassign roles from Step 3
az role assignment list --assignee <your-principal-id>
```

**401 Unauthorized:**
```bash
# Azure CLI not logged in
# Solution: Login and set subscription
az login
az account set --subscription <subscription-id>
az account show
```

**404 Not Found:**
```bash
# Resource name incorrect in environment variables
# Solution: Verify resource names in Azure Portal
az resource list --resource-group <rg-name> --output table
```

**500 Internal Server Error:**
```bash
# Check backend terminal for Python stack traces
# Common causes:
# - Missing environment variables
# - Database connection failures
# - Azure service access issues
```

### Frontend Issues

#### React App Shows Blank Page

1. Check browser console (F12) for JavaScript errors
2. Verify `REACT_APP_API_BASE_URL` in `src/App/.env`
3. Clear browser cache or try incognito mode
4. Verify backend is running and accessible at `http://127.0.0.1:8000`

```bash
# Test backend from browser console
fetch('http://127.0.0.1:8000/health')
  .then(r => r.json())
  .then(d => console.log(d))
```

#### API Calls Failing in Frontend

```bash
# Check CORS configuration
# Look for CORS errors in browser console (F12 → Console tab)

# Verify backend CORS settings allow localhost:3000
# Check src/api/app.py for CORS middleware configuration
```

**CORS Error Example:**
```
Access to fetch at 'http://127.0.0.1:8000/api/...' from origin 'http://localhost:3000' 
has been blocked by CORS policy
```

**Solution:** Verify CORS middleware in `src/api/app.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Azure AD Authentication Errors

```bash
# Common MSAL errors in frontend

# Error: AADSTS900561 - Endpoint only accepts POST
# Solution: Configure app registration as SPA (Single-Page Application)
# Azure Portal → App Registrations → Your App → Authentication
# Add platform: Single-page application with redirect URI http://localhost:3000

# Error: AADSTS50011 - Redirect URI mismatch
# Solution: Add http://localhost:3000 to redirect URIs in app registration
```

### Network and Firewall Issues

```bash
# Test if ports are accessible
# Windows:
Test-NetConnection -ComputerName localhost -Port 8000
Test-NetConnection -ComputerName localhost -Port 3000

# Linux/macOS:
nc -zv localhost 8000
nc -zv localhost 3000

# Check if firewall is blocking
# Windows: Windows Defender Firewall → Allow an app
# Linux: sudo ufw status
```

### Git Issues

#### Clone or Pull Failures

```bash
# SSL certificate issues
git config --global http.sslVerify false  # Temporary - not recommended for production

# Or configure proper certificate
git config --global http.sslCAInfo /path/to/certificate.crt

# Authentication issues
git config --global credential.helper wincred  # Windows
git config --global credential.helper cache    # Linux/macOS

# Large files timeout
git config --global http.postBuffer 524288000  # 500MB
```

#### Merge Conflicts

```bash
# View conflicted files
git status

# Abort merge if needed
git merge --abort

# Or resolve conflicts manually and commit
git add <resolved-files>
git commit -m "Resolved merge conflicts"
```

### Performance Issues

#### Slow Backend Response

```bash
# Check Application Insights for performance metrics
# Enable profiling in .env
PROFILING_ENABLED=true

# Monitor Azure resource metrics
# First, get the resource ID of the service you want to monitor
az resource show --name <resource-name> --resource-group <rg-name> --resource-type <type> --query id -o tsv

# List available metrics for a resource
az monitor metrics list-definitions --resource <resource-id>

# View specific metric data
az monitor metrics list \
  --resource <resource-id> \
  --metric-names <metric-name>
```

#### High Memory Usage

```bash
# Monitor Python process
# Windows:
Get-Process python | Select-Object Name, CPU, WorkingSet

# Linux/macOS:
ps aux | grep python
top -p $(pgrep python)

# If memory issues persist:
# - Reduce batch sizes in data processing
# - Clear Cosmos DB cache
# - Restart backend service
```

### Getting Additional Help

If issues persist after trying the troubleshooting steps:

1. **Check Logs:**
   - Backend API logs in Terminal 1
   - Frontend logs in Terminal 2
   - Browser console (F12) for frontend errors
   - Azure Portal → Application Insights for production issues

2. **Collect Diagnostic Information:**
   ```bash
   # System info
   python --version
   node --version
   npm --version
   az --version
   
   # Azure login status
   az account show
   
   # Environment variables (sanitize before sharing)
   env | grep AZURE | sed 's/=.*/=***/'
   ```

3. **Review Documentation:**
   - [TroubleShootingSteps.md](./TroubleShootingSteps.md)
   - [DeploymentGuide.md](./DeploymentGuide.md)
   - [Azure Account Setup](./AzureAccountSetUp.md)

4. **GitHub Issues:**
   - Search existing issues: [GitHub Issues](https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/issues)
   - Create new issue with diagnostic information

5. **Azure Support:**
   - For Azure-specific issues: [Azure Support](https://azure.microsoft.com/support/)
   - Check Azure service health: [Azure Status](https://status.azure.com/)

---

## Step 7: Next Steps

Once all services are running (as confirmed in Step 6), you can:

1. **Explore the Application**: Navigate through the UI at `http://localhost:3000` to explore conversational insights
2. **Try Sample Queries**: Follow [SampleQuestions.md](./SampleQuestions.md) for example queries you can ask the system
3. **Understand the Architecture**: Review [TechnicalArchitecture.md](./TechnicalArchitecture.md) to understand how the system processes conversations
4. **Customize Your Data**: Follow [CustomizeData.md](./CustomizeData.md) to learn how to import your own conversation data
5. **Deploy to Azure**: When ready for production, use [DeploymentGuide.md](./DeploymentGuide.md) to deploy the full solution
6. **Explore the Codebase**:
   - Backend agents: `src/api/agents/`
   - API routes: `src/api/api/`
   - Services: `src/api/services/`
   - React components: `src/App/src/components/`

---

## Related Documentation

• [Deployment Guide](./DeploymentGuide.md) - Production deployment instructions using Azure Developer CLI  
• [Technical Architecture](./TechnicalArchitecture.md) - System architecture and component overview  
• [Customize Data](./CustomizeData.md) - Import and process your own conversation data  
• [Sample Questions](./SampleQuestions.md) - Example queries for testing the system  
• [Troubleshooting Steps](./TroubleShootingSteps.md) - Common issues and solutions  
• [Azure Account Setup](./AzureAccountSetUp.md) - Azure subscription and quota requirements

---
