# Deployment Guide

## Overview

This guide walks you through deploying the Conversation Knowledge Mining Solution Accelerator to Azure. The deployment process takes approximately 10-20 minutes and includes both infrastructure provisioning and application setup.

🆘 **Need Help?** If you encounter any issues during deployment, check our [Troubleshooting Guide](./TroubleShootingSteps.md) for solutions to common problems.

> **Note**: Some tenants may have additional security restrictions that run periodically and could impact the application (e.g., blocking public network access). If you experience issues or the application stops working, check if these restrictions are the cause.

## Step 1: Prerequisites & Setup

### 1.1 Azure Account Requirements

Ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the following permissions:

| **Required Permission/Role** | **Scope** | **Purpose** |
|------------------------------|-----------|-------------|
| **Contributor** | Subscription level | Create and manage Azure resources |
| **User Access Administrator** | Subscription level | Manage user access and role assignments |
| **Role Based Access Control Admin** | Subscription/Resource Group level | Configure RBAC permissions |
| **App Registration Creation** | Microsoft Entra ID | Create and configure authentication (optional) |

**🔍 How to Check Your Permissions:**

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **Subscriptions** (search for "subscriptions" in the top search bar)
3. Click on your target subscription
4. In the left menu, click **Access control (IAM)**
5. Scroll down to see the table with your assigned roles - you should see:
   - **Contributor**
   - **User Access Administrator**
   - **Role Based Access Control Administrator** (or similar RBAC role)

📖 **Detailed Setup:** Follow [Azure Account Set Up](./AzureAccountSetUp.md) for complete configuration.

### 1.2 Check Service Availability & Quota

⚠️ **CRITICAL:** Before proceeding, ensure your chosen region has all required services available:

**Required Azure Services:**
- [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Azure AI Content Understanding](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/)
- [Azure AI Search](https://learn.microsoft.com/en-us/azure/search/)
- [Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/)
- [Azure Container Registry](https://learn.microsoft.com/en-us/azure/container-registry/)
- [Azure SQL Database](https://learn.microsoft.com/en-us/azure/azure-sql/database/)
- [Azure Blob Storage](https://learn.microsoft.com/en-us/azure/storage/blobs/)
- [Azure Queue Storage](https://learn.microsoft.com/en-us/azure/storage/queues/)
- [GPT Model Capacity](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models)

**Recommended Regions:** Australia East, Sweden Central, Southeast Asia

🔍 **Check Availability:** Use [Azure Products by Region](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/) to verify service availability.

### 1.3 Quota Check (Optional)

💡 **RECOMMENDED:** Check your Azure OpenAI quota availability before deployment for optimal planning.

📖 **Follow:** [Quota Check Instructions](./quota_check.md) to ensure sufficient capacity.

**Default Quota Configuration:**
- **gpt-5.2 (150k tokens)** — backs the chat agent and insights generation.
- **text-embedding-3-small (80k tokens)** — backs document embedding for hybrid search.

> **Note:** When you run `azd up`, the deployment will automatically show you regions with available quota, so this pre-check is optional but helpful for planning purposes. You can customize these settings later in [Step 3.2: Advanced Configuration](#32-advanced-configuration-optional).

## Step 2: Choose Your Deployment Environment

Select one of the following options to deploy the Conversation Knowledge Mining Solution Accelerator:

### Environment Comparison

| **Option** | **Best For** | **Prerequisites** | **Setup Time** |
|------------|--------------|-------------------|----------------|
| **GitHub Codespaces** | Quick deployment, no local setup required | GitHub account | ~3-5 minutes |
| **VS Code Dev Containers** | Fast deployment with local tools | Docker Desktop, VS Code | ~5-10 minutes |
| **VS Code Web** | Quick deployment, no local setup required | Azure account | ~2-4 minutes |
| **Local Environment** | Enterprise environments, full control | All tools individually | ~15-30 minutes |

**💡 Recommendation:** For fastest deployment, start with **GitHub Codespaces** - no local installation required.

---

<details>
<summary><b>Option A: GitHub Codespaces (Easiest)</b></summary>

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator)

1. Click the badge above (may take several minutes to load)
2. Accept default values on the Codespaces creation page
3. Wait for the environment to initialize (includes all deployment tools)
4. Proceed to [Step 3: Configure Deployment Settings](#step-3-configure-deployment-settings)

</details>

<details>
<summary><b>Option B: VS Code Dev Containers</b></summary>

[![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator)

**Prerequisites:**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- [VS Code](https://code.visualstudio.com/) with [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

**Steps:**
1. Start Docker Desktop
2. Click the badge above to open in Dev Containers
3. Wait for the container to build and start (includes all deployment tools)
4. Proceed to [Step 3: Configure Deployment Settings](#step-3-configure-deployment-settings)

</details>

<details>
<summary><b>Option C: Visual Studio Code Web</b></summary>

[![Open in Visual Studio Code Web](https://img.shields.io/static/v1?style=for-the-badge&label=Visual%20Studio%20Code%20(Web)&message=Open&color=blue&logo=visualstudiocode&logoColor=white)](https://vscode.dev/azure/?vscode-azure-exp=foundry&agentPayload=eyJiYXNlVXJsIjogImh0dHBzOi8vcmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbS9taWNyb3NvZnQvQ29udmVyc2F0aW9uLUtub3dsZWRnZS1NaW5pbmctU29sdXRpb24tQWNjZWxlcmF0b3IvcmVmcy9oZWFkcy9tYWluL2luZnJhL3ZzY29kZV93ZWIiLCAiaW5kZXhVcmwiOiAiL2luZGV4Lmpzb24iLCAidmFyaWFibGVzIjogeyJhZ2VudElkIjogIiIsICJjb25uZWN0aW9uU3RyaW5nIjogIiIsICJ0aHJlYWRJZCI6ICIiLCAidXNlck1lc3NhZ2UiOiAiIiwgInBsYXlncm91bmROYW1lIjogIiIsICJsb2NhdGlvbiI6ICIiLCAic3Vic2NyaXB0aW9uSWQiOiAiIiwgInJlc291cmNlSWQiOiAiIiwgInByb2plY3RSZXNvdXJjZUlkIjogIiIsICJlbmRwb2ludCI6ICIifSwgImNvZGVSb3V0ZSI6IFsiYWktcHJvamVjdHMtc2RrIiwgInB5dGhvbiIsICJkZWZhdWx0LWF6dXJlLWF1dGgiLCAiZW5kcG9pbnQiXX0=)

1. Click the badge above (may take a few minutes to load)
2. Sign in with your Azure account when prompted
3. Select the subscription where you want to deploy the solution
4. Wait for the environment to initialize (includes all deployment tools)
5. **Authenticate with Azure** (VS Code Web requires device code authentication):
   ```shell
   az login --use-device-code
   ```
   > **Note:** In VS Code Web environment, the regular `az login` command may fail. Use the `--use-device-code` flag to authenticate via device code flow. Follow the prompts in the terminal to complete authentication.
6. Proceed to [Step 3: Configure Deployment Settings](#step-3-configure-deployment-settings)

</details>

<details>
<summary><b>Option D: Local Environment</b></summary>

**Required Tools:**
- [PowerShell 7.0+](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell)
- [Azure Developer CLI (azd) 1.18.0+](https://aka.ms/install-azd)
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
- [Python 3.9+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)

**Setup Steps:**
1. Install all required deployment tools listed above
2. Clone the repository:

   ```shell
   git clone https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator.git
   cd Conversation-Knowledge-Mining-Solution-Accelerator
   ```

3. Proceed to [Step 3: Configure Deployment Settings](#step-3-configure-deployment-settings)

**PowerShell Users:** If you encounter script execution issues, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

</details>

## Step 3: Configure Deployment Settings

Review the configuration options below. You can customize any settings that meet your needs, or leave them as defaults to proceed with a standard deployment.

### 3.1 Default Configuration

By default, `azd up` provisions the following resources:

| Resource | Default SKU / Size |
|----------|--------------------|
| Azure AI Services (OpenAI) | gpt-5.2 (2025-12-11), text-embedding-3-small |
| Azure AI Search | Standard (S1) |
| Azure App Service Plan | B2 (backend), B2 (frontend) |
| Azure SQL Database | Basic (5 DTU) |
| Azure Container Registry | Basic |
| Azure Storage Account | LRS |
| Azure AI Foundry Hub + Project | Standard |

### 3.2 Advanced Configuration (Optional)

<details>
<summary><b>Configurable Parameters</b></summary>

You can customize various deployment settings before running `azd up`, including Azure regions, AI model configurations (deployment type, version, capacity), and resource names.

📖 **Complete Guide:** See [Customizing azd Parameters](./CustomizingAzdParameters.md) for the full list of available parameters and their usage.

</details>

<details>
<summary><b>[Optional] Quota Recommendations</b></summary>

By default, the **GPT model capacity** in deployment is set to **150k tokens** and the **embedding model capacity** to **80k tokens**.

To adjust quota settings, follow the [Quota Check Instructions](./quota_check.md).

**⚠️ Warning:** Insufficient quota can cause deployment errors. Please ensure you have the recommended capacity or request additional capacity before deploying this solution.

</details>

## Step 4: Deploy the Solution

💡 **Before You Start:** If you encounter any issues during deployment, check our [Troubleshooting Guide](./TroubleShootingSteps.md) for common solutions.

⚠️ **Critical: Redeployment Warning** - If you have previously run `azd up` in this folder (i.e., a `.azure` folder exists), you must [create a fresh environment](#creating-a-new-environment) to avoid conflicts and deployment failures.

### 4.1 Authenticate with Azure

Sign in with **both** the Azure Developer CLI and the Azure CLI. `azd` provisions the infrastructure, and the post-provision scripts use the Azure CLI (`az acr build`, `az webapp`, etc.) — the two tools keep separate credential stores, so you need to log in to each.

```shell
azd auth login
az login
```

**Alternatively, login using a device code (recommended when using VS Code Web):**
```shell
az login --use-device-code
```

**For specific tenants:**
```shell
azd auth login --tenant-id <tenant-id>
az login --tenant <tenant-id>
```

**Finding Tenant ID:**
1. Open the [Azure Portal](https://portal.azure.com/)
2. Navigate to **Microsoft Entra ID** from the left-hand menu
3. Under the **Overview** section, locate the **Tenant ID** field. Copy the value displayed

### 4.2 Start Deployment

```shell
azd up
```

**During deployment, you'll be prompted for:**
1. **Environment name** (e.g., "kmdev") - Must be 3-16 characters long, alphanumeric only
2. **Azure subscription** selection
3. **Azure region** - Select a region with available model quota for AI operations
4. **Resource group** selection (create new or use existing)

**Expected Duration:** 10-20 minutes for default configuration

`azd up` runs the hooks defined in [azure.yaml](../azure.yaml) and performs the following steps automatically — no separate manual deploy step is required:

1. **Pre-provision** — Generates and stores an `ADMIN_API_KEY` in the `azd` environment.
2. **Provision** — Creates all Azure resources using the Bicep templates in `infra/`. The backend and frontend App Services start with a temporary placeholder image.
3. **Post-provision** — Runs automatically after provisioning:
   - Builds and pushes the API and web images to ACR and points the App Services at them ([infra/scripts/build/build_and_push_images.ps1](../infra/scripts/build/build_and_push_images.ps1))
   - Writes the `azd` environment values to a local `.env` file
   - Creates a Python virtual environment and installs [infra/scripts/post-provision/requirements.txt](../infra/scripts/post-provision/requirements.txt)
   - Grants the API managed identity access to Azure SQL ([setup-sql-roles.ps1](../infra/scripts/post-provision/setup-sql-roles.ps1))
   - Presents the interactive data setup menu ([setup-data.ps1](../infra/scripts/post-provision/setup-data.ps1)), which prompts you to **select a scenario**. Based on your choice it uploads the sample dataset, **creates the Azure AI Foundry agents**, and wires up the search index and SQL connections. See [Step 5.2](#52-run-post-deployment-data-setup) for details.

**⚠️ Deployment Issues:** If you encounter errors or timeouts, try a different region as there may be capacity constraints. For detailed error solutions, see our [Troubleshooting Guide](./TroubleShootingSteps.md).

### 4.3 Get Application URL

After successful deployment, the post-provision hook prints the frontend URL (`Open: https://...`). The following values are also written to the `azd` environment and can be retrieved with `azd env get-values`:

| Output | Description |
|--------|-------------|
| `WEB_APP_URL` / `SERVICE_FRONTEND_URI` | Frontend web application URL |
| `API_APP_URL` / `SERVICE_BACKEND_URI` | Backend API URL |

You can also retrieve the URL from the Azure Portal:
1. Open [Azure Portal](https://portal.azure.com/)
2. Navigate to your resource group
3. Find the Frontend App Service (name starts with `app-`)
4. Copy the **Default domain**

## Step 5: Post-Deployment Configuration

> **Note:** For this solution, the post-deployment steps below (building images and running data setup) are executed **automatically** by the `azd up` post-provision hook. This section documents what those steps do and how to **re-run them manually** if needed (for example, after a code change or to switch scenarios).

### 5.1 Build and Push Container Images

This solution provisions a dedicated **Azure Container Registry (ACR)** in your resource group. Image building is integrated into the `azd up` **postprovision** hook and runs automatically. The images are **built remotely in ACR using `az acr build`**. If you need to rebuild and push images manually (for example, after a code change), run:

- **Windows (PowerShell):**
  ```powershell
  ./infra/scripts/build/build_and_push_images.ps1
  ```

* **Linux / macOS:**
  ```bash
  pwsh ./infra/scripts/build/build_and_push_images.ps1
  ```

**What the script does:**
- Builds the Backend (API) image from [src/api/ApiApp.Dockerfile](../src/api/ApiApp.Dockerfile)
- Builds the Frontend (Web) image from [src/app/WebApp.Dockerfile](../src/app/WebApp.Dockerfile)
- Pushes both images to the provisioned Azure Container Registry
- Updates the backend and frontend App Services to run the new images and restarts them

**Expected Processing Time:** 5-10 minutes depending on network speed.

### 5.2 Run Post Deployment Data Setup

During the `azd up` postprovision hook, an interactive data setup menu is presented. You can also run it manually at any time from the project root:

- **Windows (PowerShell):**
  ```powershell
  ./infra/scripts/post-provision/setup-data.ps1
  ```

* **Linux / macOS:**
  ```bash
  pwsh ./infra/scripts/post-provision/setup-data.ps1
  ```

The system presents available scenarios for selection:

**Prerequisites:** Option 5 — Microsoft Fabric requires **Admin** role on the target Fabric workspace for your `az login` identity, so the setup script can grant the API's managed identity Contributor access there.

```
============================================
 Conversation Knowledge Mining - Setup Menu
============================================

  1. Contact Center (JSON transcripts + pre-indexed data)
  2. Mortgage Application (PDF documents)
  3. Telecom Analysis (JSON transcripts + WAV recordings)
  4. Connect to Azure AI Search (BYOD external index)
  5. Connect to Microsoft Fabric (BYOD external warehouse)
  6. Skip (upload data manually from the web app later)

Enter your choice [1-6]:
```

Upon selection, the corresponding datasets and configuration files are uploaded, the Azure AI Foundry agents (a ChatAgent for grounded Q&A and a SummaryAgent that generates concise chat conversation titles) are created, and connections are configured.

> **Option 6 — Skip (upload your own files later):** Choosing **Skip** loads no sample data. You can upload your own files directly from the web application's **Home** page at any time. Supported formats: **PDF, DOCX, JSON, CSV, TXT, images (PNG/JPG), WAV, MP3**.

**Non-interactive usage:**
```powershell
./infra/scripts/post-provision/setup-data.ps1 -Scenario contact-center
./infra/scripts/post-provision/setup-data.ps1 -Scenario mortgage-application
./infra/scripts/post-provision/setup-data.ps1 -Scenario telecom-analysis
```

### 5.3 Access the Application

Once deployment and data setup complete, access your deployed frontend application at the URL from [Step 4.3](#43-get-application-url).

### 5.4 Configure Authentication (Optional)

By default, the application is accessible without authentication (suitable for development and testing). For production deployments, enable Microsoft Entra ID authentication:

1. Follow [App Authentication Configuration](./AppAuthentication.md)
2. Wait up to 10 minutes for authentication changes to take effect

### 5.5 Verify Deployment

1. Access your application using the URL from Step 4.3
2. Confirm the application loads successfully
3. If you loaded a sample scenario, navigate to **Explore** to chat with your data or **Insights** to view the auto-generated dashboard

### 5.6 Test the Application

**Quick Test Steps:**

1. **Access the application** using the URL from Step 4.3
2. **Select a scenario** or upload your own data from the **Home** page
3. **Ask a sample question** relevant to the loaded scenario
4. **Verify the response** includes grounded, structured answers with citations
5. **Check the logs** in Azure Portal to confirm backend processing

📖 **Detailed Instructions:** See the complete [Sample Questions](./SampleQuestions.md) guide for step-by-step testing procedures and sample questions for each use case.

## Step 6: Clean Up (Optional)

### Remove All Resources

To purge resources and clean up after deployment, use the `azd down` command:

```shell
azd down
```

To also purge soft-deleted Azure AI and Key Vault resources (prevents name conflicts on re-deployment):

```shell
azd down --purge
```

> **Note:** `azd down` permanently deletes all resource groups, data, and deployed agents. This action cannot be undone. Export any data you need before running this command.

## Managing Multiple Environments

### Recover from Failed Deployment

<details>
<summary><b>Recover from Failed Deployment</b></summary>

**If your deployment failed or encountered errors:**

1. **Try a different region:** Create a new environment and select a different Azure region during deployment
2. **Clean up and retry:** Use `azd down` to remove failed resources, then `azd up` to redeploy
3. **Check troubleshooting:** Review [Troubleshooting Guide](./TroubleShootingSteps.md) for specific error solutions
4. **Fresh start:** Create a completely new environment with a different name

**Example Recovery Workflow:**
```shell
# Remove failed deployment (optional)
azd down

# Create new environment (3-16 chars, alphanumeric only)
azd env new kmretry

# Deploy with different settings/region
azd up
```

</details>

### Creating a New Environment

<details>
<summary><b>Create a New Environment</b></summary>

**Create Environment Explicitly:**
```shell
# Create a new named environment (3-16 characters, alphanumeric only)
azd env new <new-environment-name>

# Select the new environment
azd env select <new-environment-name>

# Deploy to the new environment
azd up
```

> **Environment Name Requirements:**
> - **Length:** 3-16 characters
> - **Characters:** Alphanumeric only (letters and numbers)
> - **Valid examples:** `kmdev`, `test123`, `myappdev`, `prod2025`
> - **Invalid examples:** `co` (too short), `my-very-long-environment-name` (too long), `test_env` (underscore not allowed)

</details>

<details>
<summary><b>Switch Between Environments</b></summary>

**List Available Environments:**
```shell
azd env list
```

**Switch to Different Environment:**
```shell
azd env select <environment-name>
```

**View Current Environment:**
```shell
azd env get-values
```

</details>

### Best Practices for Multiple Environments

- **Use descriptive names:** `kmdev`, `kmprod`, `kmtest` (remember: 3-16 chars, alphanumeric only)
- **Different regions:** Deploy to multiple regions for testing quota availability
- **Separate configurations:** Each environment can have different parameter settings
- **Clean up unused environments:** Use `azd down` to remove environments you no longer need

## Next Steps

Now that your deployment is complete and tested, explore these resources to enhance your experience:

📚 **Learn More:**
- [Sample Questions](./SampleQuestions.md) - Explore sample questions and workflows
- [Customizing azd Parameters](./CustomizingAzdParameters.md) - Advanced configuration options
- [App Authentication Setup](./AppAuthentication.md) - Secure your application
- [Azure Account Setup](./AzureAccountSetUp.md) - Detailed Azure subscription configuration

## Need Help?

- 🐛 **Issues:** Check [Troubleshooting Guide](./TroubleShootingSteps.md)
- 💬 **Support:** [Submit a new issue](https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/issues)
