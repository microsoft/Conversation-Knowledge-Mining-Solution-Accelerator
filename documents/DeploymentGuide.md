# Deployment Guide

## Overview

This guide walks you through deploying the Conversation Knowledge Mining Solution Accelerator to Azure. The deployment process takes approximately 10-15 minutes for the default Development/Testing configuration and includes both infrastructure provisioning and application setup.

🆘 **Need Help?** If you encounter any issues during deployment, check our [Troubleshooting Guide](./TroubleShootingSteps.md) for solutions to common problems.

## Step 1: Prerequisites & Setup

### 1.1 Azure Account Requirements

Ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the following permissions:

| **Required Permission/Role** | **Scope** | **Purpose** |
|------------------------------|-----------|-------------|
| **Contributor** | Subscription level | Create and manage Azure resources |
| **User Access Administrator** | Subscription level | Manage user access and role assignments |
| **Role Based Access Control** | Subscription/Resource Group level | Configure RBAC permissions |
| **Application Administrator** | Tenant | Create app registrations for authentication |

**🔍 How to Check Your Permissions:**

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **Subscriptions** (search for "subscriptions" in the top search bar)
3. Click on your target subscription
4. In the left menu, click **Access control (IAM)**
5. Scroll down to see the table with your assigned roles - you should see:
   - **Contributor** 
   - **User Access Administrator**
   - **Role Based Access Control Administrator** (or similar RBAC role)

**For App Registration permissions:**
1. Go to **Microsoft Entra ID** → **Manage** → **App registrations**
2. Try clicking **New registration** 
3. If you can access this page, you have the required permissions
4. Cancel without creating an app registration

📖 **Detailed Setup:** Follow [Azure Account Set Up](./AzureAccountSetUp.md) for complete configuration.

### 1.2 Check Service Availability & Quota

⚠️ **CRITICAL:** Before proceeding, ensure your chosen region has all required services available:

**Required Azure Services:**

- [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry)
- [Azure AI Content Understanding Service](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [GPT Model Capacity](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models)
- [Azure AI Search](https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search)
- [Azure SQL Database](https://learn.microsoft.com/en-us/azure/azure-sql/database/sql-database-paas-overview)
- [Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/introduction)
- [Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Azure Container Registry](https://learn.microsoft.com/en-us/azure/container-registry/)
- [Embedding Deployment Capacity](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models#embedding-models)
- [Azure Semantic Search](./AzureSemanticSearchRegion.md)

**Recommended Regions:** East US, East US2, Australia East, UK South, France Central

🔍 **Check Availability:** Use [Azure Products by Region](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/) to verify service availability.

### 1.3 Quota Check (Optional)

💡 **RECOMMENDED:** Check your Azure OpenAI quota availability before deployment for optimal planning.

📖 **Follow:** [Quota Check Instructions](./QuotaCheck.md) to ensure sufficient capacity.

**Recommended Configuration:**
- **Default:** 150k tokens (minimum)
- **Optimal:** More than 150k tokens (recommended for best performance)

> **Note:** When you run `azd up`, the deployment will automatically show you regions with available quota, so this pre-check is optional but helpful for planning purposes. You can customize these settings later in [Step 3.3: Advanced Configuration](#33-advanced-configuration-optional).

📖 **Adjust Quota:** Follow [Azure GPT Quota Settings](./AzureGPTQuotaSettings.md) if needed.

## Step 2: Choose Your Deployment Environment

Select one of the following options to deploy the Conversational Knowledge Mining Solution Accelerator:

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

 [![Open in Visual Studio Code Web](https://img.shields.io/static/v1?style=for-the-badge&label=Visual%20Studio%20Code%20(Web)&message=Open&color=blue&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/azure/?vscode-azure-exp=foundry&agentPayload=eyJiYXNlVXJsIjogImh0dHBzOi8vcmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbS9taWNyb3NvZnQvQ29udmVyc2F0aW9uLUtub3dsZWRnZS1NaW5pbmctU29sdXRpb24tQWNjZWxlcmF0b3IvcmVmcy9oZWFkcy9tYWluL2luZnJhL3ZzY29kZV93ZWIiLCAiaW5kZXhVcmwiOiAiL2luZGV4Lmpzb24iLCAidmFyaWFibGVzIjogeyJhZ2VudElkIjogIiIsICJjb25uZWN0aW9uU3RyaW5nIjogIiIsICJ0aHJlYWRJZCI6ICIiLCAidXNlck1lc3NhZ2UiOiAiIiwgInBsYXlncm91bmROYW1lIjogIiIsICJsb2NhdGlvbiI6ICIiLCAic3Vic2NyaXB0aW9uSWQiOiAiIiwgInJlc291cmNlSWQiOiAiIiwgInByb2plY3RSZXNvdXJjZUlkIjogIiIsICJlbmRwb2ludCI6ICIifSwgImNvZGVSb3V0ZSI6IFsiYWktcHJvamVjdHMtc2RrIiwgInB5dGhvbiIsICJkZWZhdWx0LWF6dXJlLWF1dGgiLCAiZW5kcG9pbnQiXX0=)

1. Click the badge above (may take a few minutes to load)
2. Sign in with your Azure account when prompted
3. Select the subscription where you want to deploy the solution
4. Wait for the environment to initialize (includes all deployment tools)
5. Once the solution opens, the **AI Foundry terminal** will automatically start running the following command to install the required dependencies:

    ```shell
    sh install.sh
    ```
    During this process, you'll be prompted with the message:
    ```
    What would you like to do with these files?
    - Overwrite with versions from template
    - Keep my existing files unchanged
    ```
    Choose "**Overwrite with versions from template**" and provide a unique environment name when prompted.
6. Proceed to [Step 3: Configure Deployment Settings](#step-3-configure-deployment-settings)

</details>

<details>
<summary><b>Option D: Local Environment</b></summary>

**Required Tools:**
- [PowerShell 7.0+](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell) 
- [Azure Developer CLI (azd) 1.18.0+](https://aka.ms/install-azd)
- [Python 3.9+](https://www.python.org/downloads/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Git](https://git-scm.com/downloads)

**Setup Steps:**
1. Install all required deployment tools listed above
2. Clone the repository:
   ```shell
   azd init -t microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/
   ```
3. Open the project folder in your terminal
4. Proceed to [Step 3: Configure Deployment Settings](#step-3-configure-deployment-settings)

**PowerShell Users:** If you encounter script execution issues, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

</details>

## Step 3: Configure Deployment Settings

Review the configuration options below. You can customize any settings that meet your needs, or leave them as defaults to proceed with a standard deployment.

### 3.1 Choose Deployment Type (Optional)

| **Aspect** | **Development/Testing (Default)** | **Production** |
|------------|-----------------------------------|----------------|
| **Configuration File** | `main.parameters.json` (sandbox) | Copy `main.waf.parameters.json` to `main.parameters.json` |
| **Security Controls** | Minimal (for rapid iteration) | Enhanced (production best practices) |
| **Cost** | Lower costs | Cost optimized |
| **Use Case** | POCs, development, testing | Production workloads |
| **Framework** | Basic configuration | [Well-Architected Framework](https://learn.microsoft.com/en-us/azure/well-architected/) |
| **Features** | Core functionality | Reliability, security, operational excellence |

**To use production configuration:**

Copy the contents from the production configuration file to your main parameters file:

1. Navigate to the `infra` folder in your project
2. Open `main.waf.parameters.json` in a text editor (like Notepad, VS Code, etc.)
3. Select all content (Ctrl+A) and copy it (Ctrl+C)
4. Open `main.parameters.json` in the same text editor
5. Select all existing content (Ctrl+A) and paste the copied content (Ctrl+V)
6. Save the file (Ctrl+S)

### 3.2 Set VM Credentials (Optional - Production Deployment Only)

> **Note:** This section only applies if you selected **Production** deployment type in section 3.1. VMs are not deployed in the default Development/Testing configuration.

By default, random GUIDs are generated for VM credentials. To set custom credentials:

```shell
azd env set AZURE_ENV_VM_ADMIN_USERNAME <your-username>
azd env set AZURE_ENV_VM_ADMIN_PASSWORD <your-password>
```

### 3.3 Advanced Configuration (Optional)

<details>
<summary><b>Configurable Parameters</b></summary>

You can customize various deployment settings before running `azd up`, including Azure regions, AI model configurations (deployment type, version, capacity), container registry settings, and resource names.

📖 **Complete Guide:** See [Parameter Customization Guide](./CustomizingAzdParameters.md) for the full list of available parameters and their usage.

</details>

<details>
<summary><b>Reuse Existing Resources</b></summary>

To optimize costs and integrate with your existing Azure infrastructure, you can configure the solution to reuse compatible resources already deployed in your subscription.

**Supported Resources for Reuse:**

- **Log Analytics Workspace:** Integrate with your existing monitoring infrastructure by reusing an established Log Analytics workspace for centralized logging and monitoring. [Configuration Guide](./re-use-log-analytics.md)

- **Azure AI Foundry Project:** Leverage your existing AI Foundry project and deployed models to avoid duplication and reduce provisioning time. [Configuration Guide](./re-use-foundry-project.md)

**Key Benefits:**
- **Cost Optimization:** Eliminate duplicate resource charges
- **Operational Consistency:** Maintain unified monitoring and AI infrastructure
- **Faster Deployment:** Skip resource creation for existing compatible services
- **Simplified Management:** Reduce the number of resources to manage and monitor

**Important Considerations:**
- Ensure existing resources meet the solution's requirements and are in compatible regions
- Review access permissions and configurations before reusing resources
- Consider the impact on existing workloads when sharing resources

</details>

## Step 4: Deploy the Solution

💡 **Before You Start:** If you encounter any issues during deployment, check our [Troubleshooting Guide](./TroubleShootingSteps.md) for common solutions.

### 4.1 Authenticate with Azure

```shell
azd auth login
```

**For specific tenants:**
```shell
azd auth login --tenant-id <tenant-id>
```

> **Finding Tenant ID:** 
   > 1. Open the [Azure Portal](https://portal.azure.com/).
   > 2. Navigate to **Microsoft Entra ID** from the left-hand menu.
   > 3. Under the **Overview** section, locate the **Tenant ID** field. Copy the value displayed.

### 4.2 Start Deployment

```shell
azd up
```

**During deployment, you'll be prompted for:**
1. **Environment name** (e.g., "ckmapp") - Must be 3-20 characters long, lowercase alphanumeric only
2. **Azure subscription** selection
3. **Azure AI Foundry deployment region** - Select a region with available gpt-4o model quota for AI operations
4. **Primary location** - Select the region where your infrastructure resources will be deployed
5. **Resource group** selection (create new or use existing)
6. **Use case** selection:
   - `telecom` - For telecommunications conversation data
   - `IT_helpdesk` - For IT helpdesk conversation data

**Expected Duration:** 7-10 minutes for default configuration

**⚠️ Deployment Issues:** If you encounter errors or timeouts, try a different region as there may be capacity constraints. For detailed error solutions, see our [Troubleshooting Guide](./TroubleShootingSteps.md).

### 4.3 Get Application URL

After successful deployment:
1. Open [Azure Portal](https://portal.azure.com/)
2. Navigate to your resource group
3. Find the App Service with "app-" in the name
4. Copy the **Default domain**

⚠️ **Important:** Complete the following steps to process sample data and configure authentication before accessing the application.

### 4.4 Process Sample Data

After the infrastructure deployment completes, follow these steps to process and load the sample data:

**1. Create and activate a Python virtual environment:**

```shell
python -m venv .venv
```

**2. Activate the virtual environment:**

**For Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**For Windows (Bash):**
```bash
source .venv/Scripts/activate
```

**For Linux/macOS/VS Code Web (Bash):**
```bash
source .venv/bin/activate
```

**3. Login to Azure:**

```shell
az login
```

**Alternatively, login using a device code (recommended when using VS Code Web):**
```shell
az login --use-device-code
```

**4. Run the sample data processing script:**

The `azd up` deployment output includes a ready-to-use bash script command. Look for the script in the deployment output and run it:

```bash
bash ./infra/scripts/process_sample_data.sh
```

**If you don't have `azd env` configured**, you'll need to pass parameters manually. The parameters are grouped by service for clarity:

```bash
bash ./infra/scripts/process_sample_data.sh \
  <Resource-Group-Name> <Azure-Subscription-ID> \
  <Storage-Account-Name> <Storage-Container-Name> \
  <SQL-Server-Name> <SQL-Database-Name> <Backend-User-MID-Client-ID> <Backend-User-MID-Display-Name> \
  <AI-Search-Name> <Search-Endpoint> \
  <AI-Foundry-Resource-ID> <CU-Foundry-Resource-ID> \
  <OpenAI-Endpoint> <Embedding-Model> <Deployment-Model> \
  <CU-Endpoint> <AI-Agent-Endpoint> <CU-API-Version> <Use-Case>
```

**Parameter Descriptions:**
- **Resource Group Parameters:** Resource group name and Azure subscription ID
- **Storage Parameters:** Storage account name and container name
- **SQL Parameters:** SQL server name, database name, backend user managed identity client ID and display name
- **Search Parameters:** AI Search service name and endpoint
- **AI Foundry Parameters:** AI Foundry resource ID and Content Understanding Foundry resource ID
- **OpenAI Parameters:** OpenAI endpoint, embedding model name, and deployment model name
- **Content Understanding Parameters:** CU endpoint, AI agent endpoint, CU API version
- **Use Case:** Either `telecom` or `IT_helpdesk`

> **Note:** All parameter values are available in the Azure Portal by navigating to your deployed resources, or from the `azd env get-values` command output.

**Expected Processing Time:** 5-10 minutes depending on the amount of sample data.

## Step 5: Post-Deployment Configuration

### 5.1 Configure Authentication (Required)

**This step is mandatory for application access:**

1. Follow [App Authentication Configuration](./AppAuthentication.md)
2. Wait up to 10 minutes for authentication changes to take effect

### 5.2 Verify Deployment

1. Access your application using the URL from Step 4.3
2. Confirm the application loads successfully
3. Verify you can sign in with your authenticated account

### 5.3 Test the Application

Follow the sample questions to test the conversation knowledge mining functionality:

**Quick Test Steps:**
1. Sign in to the application
2. Try sample questions from the [Sample Questions](./SampleQuestions.md) guide
3. Test the chat interface with your own questions about conversation data
4. Verify the search and filter functionality works
5. Test the analytics and visualization features

📖 **Detailed Instructions:** See the complete [Sample Questions](./SampleQuestions.md) guide for comprehensive testing procedures.

## Step 6: Clean Up (Optional)

### Remove All Resources

```shell
azd down
```

> **Note:** If you deployed with `enableRedundancy=true` and Log Analytics workspace replication is enabled, you must first disable replication before running `azd down` else resource group delete will fail. Follow the steps in [Handling Log Analytics Workspace Deletion with Replication Enabled](./LogAnalyticsReplicationDisable.md), wait until replication returns `false`, then run `azd down`.

### Manual Cleanup (if needed)

If deployment fails or you need to clean up manually:
- Follow [Delete Resource Group Guide](./DeleteResourceGroup.md)

## Managing Multiple Environments

### Recover from Failed Deployment

If your deployment failed or encountered errors, here are the steps to recover:

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

# Create new environment (3-20 chars, lowercase alphanumeric only)
azd env new ckmretry

# Deploy with different settings/region
azd up
```

</details>

### Creating a New Environment

If you need to deploy to a different region, test different configurations, or create additional environments:

<details>
<summary><b>Create a New Environment</b></summary>

**Create Environment Explicitly:**
```shell
# Create a new named environment (3-20 characters, lowercase alphanumeric only)
azd env new <new-environment-name>

# Select the new environment
azd env select <new-environment-name>

# Deploy to the new environment
azd up
```

**Example:**
```shell
# Create a new environment for production (valid: 3-20 chars)
azd env new ckmprod

# Switch to the new environment
azd env select ckmprod

# Deploy with fresh settings
azd up
```

> **Environment Name Requirements:**
> - **Length:** 3-20 characters
> - **Characters:** Lowercase alphanumeric only (letters and numbers)
> - **Valid examples:** `ckmapp`, `test123`, `myappdev`, `prod2024`
> - **Invalid examples:** `ck` (too short), `my-very-long-environment-name` (too long), `test_env` (underscore not allowed), `MyApp-Dev` (uppercase/hyphen not allowed)

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

- **Use descriptive names:** `ckmdev`, `ckmprod`, `ckmtest` (remember: 3-20 chars, lowercase alphanumeric only)
- **Different regions:** Deploy to multiple regions for testing quota availability
- **Separate configurations:** Each environment can have different parameter settings
- **Clean up unused environments:** Use `azd down` to remove environments you no longer need

## Next Steps

Now that your deployment is complete and tested, explore these resources to enhance your experience:

📚 **Learn More:**
- [Technical Architecture](./TechnicalArchitecture.md) - Understand the system design and components
- [Customize Data](./CustomizeData.md) - Use your own conversation data with the solution
- [Local Development Setup](./LocalDebuggingSetup.md) - Set up your local development environment for debugging

🔧 **Advanced Configuration:**
- [Customize AZD Parameters](./CustomizingAzdParameters.md) - Advanced parameter customization
- [Reuse Foundry Project](./re-use-foundry-project.md) - Leverage existing AI Foundry resources
- [Reuse Log Analytics](./re-use-log-analytics.md) - Integrate with existing monitoring

## Need Help?

- 🐛 **Issues:** Check [Troubleshooting Guide](./TroubleShootingSteps.md)
- 🔧 **Development:** See [Contributing Guide](../CONTRIBUTING.md)
- 🔒 **Security:** Review [Security Policy](../SECURITY.md)

---

## Advanced: Deploy Local Changes

If you've made local modifications to the code and want to deploy them to Azure, follow these steps to swap the configuration files:

> **Note:** To set up and run the application locally for development, see the [Local Development Setup Guide](./LocalDebuggingSetup.md).

### Step 1: Rename Azure Configuration Files

**In the root directory:**
1. Rename `azure.yaml` to `azure_custom2.yaml`
2. Rename `azure_custom.yaml` to `azure.yaml`

### Step 2: Rename Infrastructure Files

**In the `infra` directory:**
1. Rename `main.bicep` to `main_custom2.bicep`
2. Rename `main_custom.bicep` to `main.bicep`

### Step 3: Deploy Changes

Run the deployment command:
```shell
azd up
```

> **Note:** These custom files are configured to deploy your local code changes instead of pulling from the GitHub repository.
