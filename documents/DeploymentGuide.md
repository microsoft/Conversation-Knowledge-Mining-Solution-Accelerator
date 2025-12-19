# Deployment Guide

## **Pre-requisites**

To deploy this solution, ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the necessary permissions to create **resource groups, resources, app registrations, and assign roles at the resource group level**. This should include Contributor role at the subscription level and Role Based Access Control (RBAC) permissions at the subscription and/or resource group level. Follow the steps in [Azure Account Set Up](./AzureAccountSetUp.md).

Check the [Azure Products by Region](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/?products=all&regions=all) page and select a **region** where the following services are available:

- [Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry)
- [Azure Content Understanding Service](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [GPT Model Capacity](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models)
- [Foundry IQ](https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search)
- [Azure SQL Database](https://learn.microsoft.com/en-us/azure/azure-sql/database/sql-database-paas-overview)
- [Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/introduction)
- [Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Azure Container Registry](https://learn.microsoft.com/en-us/azure/container-registry/)
- [Embedding Deployment Capacity](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models#embedding-models)
- [Azure Semantic Search](./AzureSemanticSearchRegion.md)

Here are some example regions where the services are available: East US, East US2, Australia East, UK South, France Central.

### **Important Note for PowerShell Users**

If you encounter issues running PowerShell scripts due to the policy of not being digitally signed, you can temporarily adjust the `ExecutionPolicy` by running the following command in an elevated PowerShell session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

This will allow the scripts to run for the current session without permanently changing your system's policy.

## Deployment Options & Steps

### Sandbox or WAF Aligned Deployment Options

The [`infra`](../infra) folder of the Multi Agent Solution Accelerator contains the [`main.bicep`](../infra/main.bicep) Bicep script, which defines all Azure infrastructure components for this solution.

By default, the `azd up` command uses the [`main.parameters.json`](../infra/main.parameters.json) file to deploy the solution. This file is pre-configured for a **sandbox environment** — ideal for development and proof-of-concept scenarios, with minimal security and cost controls for rapid iteration.

For **production deployments**, the repository also provides [`main.waf.parameters.json`](../infra/main.waf.parameters.json), which applies a [Well-Architected Framework (WAF) aligned](https://learn.microsoft.com/en-us/azure/well-architected/) configuration. This option enables additional Azure best practices for reliability, security, cost optimization, operational excellence, and performance efficiency, such as:

  - Enhanced network security (e.g., Network protection with private endpoints)
  - Stricter access controls and managed identities
  - Logging, monitoring, and diagnostics enabled by default
  - Resource tagging and cost management recommendations

**How to choose your deployment configuration:**

* Use the default `main.parameters.json` file for a **sandbox/dev environment**
* For a **WAF-aligned, production-ready deployment**, copy the contents of `main.waf.parameters.json` into `main.parameters.json` before running `azd up`

---

### VM Credentials Configuration

By default, the solution sets the VM administrator username and password from environment variables.

To set your own VM credentials before deployment, use:

```sh
azd env set AZURE_ENV_VM_ADMIN_USERNAME <your-username>
azd env set AZURE_ENV_VM_ADMIN_PASSWORD <your-password>
```

> [!TIP]
> Always review and adjust parameter values (such as region, capacity, security settings and log analytics workspace configuration) to match your organization’s requirements before deploying. For production, ensure you have sufficient quota and follow the principle of least privilege for all identities and role assignments.

> [!IMPORTANT]
> The WAF-aligned configuration is under active development. More Azure Well-Architected recommendations will be added in future updates.

### Deployment Steps

Pick from the options below to see step-by-step instructions for GitHub Codespaces, VS Code Dev Containers, Local Environments, and Bicep deployments.

| [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator) | [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator) | [![Open in Visual Studio Code Web](https://img.shields.io/static/v1?style=for-the-badge&label=Visual%20Studio%20Code%20(Web)&message=Open&color=blue&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/azure/?vscode-azure-exp=foundry&agentPayload=eyJiYXNlVXJsIjogImh0dHBzOi8vcmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbS9taWNyb3NvZnQvQ29udmVyc2F0aW9uLUtub3dsZWRnZS1NaW5pbmctU29sdXRpb24tQWNjZWxlcmF0b3IvcmVmcy9oZWFkcy9tYWluL2luZnJhL3ZzY29kZV93ZWIiLCAiaW5kZXhVcmwiOiAiL2luZGV4Lmpzb24iLCAidmFyaWFibGVzIjogeyJhZ2VudElkIjogIiIsICJjb25uZWN0aW9uU3RyaW5nIjogIiIsICJ0aHJlYWRJZCI6ICIiLCAidXNlck1lc3NhZ2UiOiAiIiwgInBsYXlncm91bmROYW1lIjogIiIsICJsb2NhdGlvbiI6ICIiLCAic3Vic2NyaXB0aW9uSWQiOiAiIiwgInJlc291cmNlSWQiOiAiIiwgInByb2plY3RSZXNvdXJjZUlkIjogIiIsICJlbmRwb2ludCI6ICIifSwgImNvZGVSb3V0ZSI6IFsiYWktcHJvamVjdHMtc2RrIiwgInB5dGhvbiIsICJkZWZhdWx0LWF6dXJlLWF1dGgiLCAiZW5kcG9pbnQiXX0=) |
|---|---|---|

<details>
  <summary><b>Deploy in GitHub Codespaces</b></summary>

### GitHub Codespaces

You can run this solution using GitHub Codespaces. The button will open a web-based VS Code instance in your browser:

1. Open the solution accelerator (this may take several minutes):

    [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator)

2. Accept the default values on the create Codespaces page.
3. Open a terminal window if it is not already open.
4. Continue with the [deploying steps](#deploying-with-azd).

</details>

<details>
  <summary><b>Deploy in VS Code Dev Conatiners</b></summary>

### VS Code Dev Containers

You can run this solution in VS Code Dev Containers, which will open the project in your local VS Code using the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers):

1. Start Docker Desktop (install it if not already installed).
2. Open the project:

    [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator)

3. In the VS Code window that opens, once the project files show up (this may take several minutes), open a terminal window.
4. Continue with the [deploying steps](#deploying-with-azd).

</details>

<details>
  <summary><b>Deploy in VS Code Web</b></summary>

### VS Code Web

[![Open in Visual Studio Code Web](https://img.shields.io/static/v1?style=for-the-badge&label=Visual%20Studio%20Code%20(Web)&message=Open&color=blue&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/azure/?vscode-azure-exp=foundry&agentPayload=eyJiYXNlVXJsIjogImh0dHBzOi8vcmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbS9taWNyb3NvZnQvQ29udmVyc2F0aW9uLUtub3dsZWRnZS1NaW5pbmctU29sdXRpb24tQWNjZWxlcmF0b3IvcmVmcy9oZWFkcy9tYWluL2luZnJhL3ZzY29kZV93ZWIiLCAiaW5kZXhVcmwiOiAiL2luZGV4Lmpzb24iLCAidmFyaWFibGVzIjogeyJhZ2VudElkIjogIiIsICJjb25uZWN0aW9uU3RyaW5nIjogIiIsICJ0aHJlYWRJZCI6ICIiLCAidXNlck1lc3NhZ2UiOiAiIiwgInBsYXlncm91bmROYW1lIjogIiIsICJsb2NhdGlvbiI6ICIiLCAic3Vic2NyaXB0aW9uSWQiOiAiIiwgInJlc291cmNlSWQiOiAiIiwgInByb2plY3RSZXNvdXJjZUlkIjogIiIsICJlbmRwb2ludCI6ICIifSwgImNvZGVSb3V0ZSI6IFsiYWktcHJvamVjdHMtc2RrIiwgInB5dGhvbiIsICJkZWZhdWx0LWF6dXJlLWF1dGgiLCAiZW5kcG9pbnQiXX0=)

1. Click the badge above (may take a few minutes to load)
2. Sign in with your Azure account when prompted
3. Select the subscription where you want to deploy the solution
4. Wait for the environment to initialize (includes all deployment tools)
5. Once the solution opens, the **AI Foundry terminal** will automatically start running the following command to install the required dependencies:

    ```shell
    sh install.sh
    ```
    During this process, you’ll be prompted with the message:
    ```
    What would you like to do with these files?
    - Overwrite with versions from template
    - Keep my existing files unchanged
    ```
    Choose “**Overwrite with versions from template**” and provide a unique environment name when prompted.
6. Continue with the [deploying steps](#deploying-with-azd).

</details>

<details>
  <summary><b>Deploy in your local Environment</b></summary>

### Local Environment

If you're not using one of the above options for opening the project, then you'll need to:

1. Make sure the following tools are installed:
    - [PowerShell](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell?view=powershell-7.5) <small>(v7.0+)</small> - available for Windows, macOS, and Linux.
    - [Azure Developer CLI (azd)](https://aka.ms/install-azd) <small>(v1.18.0+)</small> - version
    - [Python 3.9+](https://www.python.org/downloads/)
    - [Docker Desktop](https://www.docker.com/products/docker-desktop/)
    - [Git](https://git-scm.com/downloads)
    - [Microsoft ODBC Driver 18](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver16) for SQL Server.

2. Clone the repository or download the project code via command-line:

    ```shell
    azd init -t microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/
    ```

3. Open the project folder in your terminal or editor.
4. Continue with the [deploying steps](#deploying-with-azd).

</details>

<br/>

Consider the following settings during your deployment to modify specific settings:

<details>
  <summary><b>Configurable Deployment Settings</b></summary>

When you start the deployment, most parameters will have **default values**, but you can update the following settings [here](../documents/CustomizingAzdParameters.md):

| **Setting**                                 | **Description**                                                                                           | **Default value**      |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ---------------------- |
| **Azure Region**                            | The region where resources will be created.                                                               | *(empty)*              |
| **Environment Name**                        | A **3–20 character alphanumeric value** used to generate a unique ID to prefix the resources.             | env\_name              |
| **Azure AI Content Understanding Location** | Region for content understanding resources.                                                               | swedencentral          |
| **Use Case**                      | Industry use case: **Contact-center** or **IT_helpdesk**.  | (empty)               |
| **Secondary Location**                      | A **less busy** region for **Azure SQL and Azure Cosmos DB**, useful in case of availability constraints. | eastus2                |
| **Deployment Type**                         | Select from a drop-down list (allowed: `Standard`, `GlobalStandard`).                                     | GlobalStandard         |
| **GPT Model**                               | Choose from **gpt-4, gpt-4o, gpt-4o-mini**.                                                               | gpt-4o-mini            |
| **GPT Model Version**                       | The version of the selected GPT model.                                                                    | 2024-07-18             |
| **OpenAI API Version**                      | The Azure OpenAI API version to use.                                                                      | 2025-01-01-preview     |
| **GPT Model Deployment Capacity**           | Configure capacity for **GPT models** (in thousands).                                                     | 30k                    |
| **Embedding Model**                         | Default: **text-embedding-ada-002**.                                                                      | text-embedding-ada-002 |
| **Embedding Model Capacity**                | Set the capacity for **embedding models** (in thousands).                                                 | 80k                    |
| **Image Tag**                               | Docker image tag to deploy. Common values: `latest_waf`, `dev`, `hotfix`.                  | latest_waf       |
| **Use Local Build**                         | Boolean flag to determine if local container builds should be used.                         | false             |
| **Existing Log Analytics Workspace**        | To reuse an existing Log Analytics Workspace ID.                                                          | *(empty)*              |
| **Existing Azure AI Foundry Project**        | To reuse an existing Azure AI Foundry Project ID instead of creating a new one.              | *(empty)*          |



</details>

<details>
  <summary><b>[Optional] Quota Recommendations</b></summary>

By default, the **Gpt-4o-mini model capacity** in deployment is set to **30k tokens**, so we recommend updating the following:

> **For Global Standard | GPT-4o-mini - increase the capacity to at least 150k tokens post-deployment for optimal performance.**

Depending on your subscription quota and capacity, you can [adjust quota settings](AzureGPTQuotaSettings.md) to better meet your specific needs. You can also [adjust the deployment parameters](CustomizingAzdParameters.md) for additional optimization.

**⚠️ Warning:** Insufficient quota can cause deployment errors. Please ensure you have the recommended capacity or request additional capacity before deploying this solution.

</details>
<details>

  <summary><b>Reusing an Existing Log Analytics Workspace</b></summary>

  Guide to get your [Existing Workspace ID](/documents/re-use-log-analytics.md)

</details>
<details>

  <summary><b>Reusing an Existing Azure AI Foundry Project</b></summary>

  Guide to get your [Existing Project ID](/documents/re-use-foundry-project.md)

</details>

### Deploying with AZD

Once you've opened the project in [Codespaces](#github-codespaces), [Dev Containers](#vs-code-dev-containers), or [locally](#local-environment), you can deploy it to Azure by following these steps:

1. Login to Azure:

    ```shell
    azd auth login
    ```

    #### To authenticate with Azure Developer CLI (`azd`), use the following command with your **Tenant ID**:

    ```sh
    azd auth login --tenant-id <tenant-id>
    ```

2. Provision and deploy all the resources:

    ```shell
    azd up
    ```

3. Provide an `azd` environment name (e.g., "ckmapp").
4. Select a subscription from your Azure account and choose a location that has quota for all the resources. 
5. Choose the use case: 
   - **Contact-center**
   - **IT_helpdesk** 

    - This deployment generally takes **7-10 minutes** to provision the resources in your account and set up the solution.
    - If you encounter an error or timeout during deployment, changing the location may help, as there could be availability constraints for the resources.

5. Once the deployment has completed successfully, copy the bash command from terminal: (ex: `bash ./infra/scripts/process_sample_data.sh`) for later use.

6. Create and activate a virtual environment in bash terminal:
  
    ```shell
    python -m venv .venv
    ```

    **For Windows (Bash):**
    ```shell
    source .venv/Scripts/activate
    ```

    **For Linux/VS Code Web (Bash):**
    ```shell
    source .venv/bin/activate
    ```

7. Login to Azure:

    ```shell
    az login
    ```

    Alternatively, login to Azure using a device code (recommended when using VS Code Web):

    ```shell
    az login --use-device-code
    ```
8. Run the bash script from the output of the azd deployment. The script will look like the following:

    ```bash
    bash ./infra/scripts/process_sample_data.sh
    ```

    If you don't have `azd env` then you need to pass parameters along with the command. Parameters are grouped by service for clarity. The command will look like the following:

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

9. Once the deployment has completed successfully, open the [Azure Portal](https://portal.azure.com/), go to the deployed resource group, find the App Service, and get the app URL from `Default domain`.

10. You can now delete the resources by running `azd down`, if you are done trying out the application.
   > **Note:** If you deployed with `enableRedundancy=true` and Log Analytics workspace replication is enabled, you must first disable replication before running `azd down` else resource group delete will fail. Follow the steps in [Handling Log Analytics Workspace Deletion with Replication Enabled](./LogAnalyticsReplicationDisable.md), wait until replication returns `false`, then run `azd down`.

### 🛠️ Troubleshooting
 If you encounter any issues during the deployment process, please refer  [troubleshooting](../documents/TroubleShootingSteps.md) document for detailed steps and solutions

## Post Deployment Steps

1. **Add App Authentication**
   
    Follow steps in [App Authentication](./AppAuthentication.md) to configure authentication in app service. Note: Authentication changes can take up to 10 minutes 

2. **Deleting Resources After a Failed Deployment**  

     - Follow steps in [Delete Resource Group](./DeleteResourceGroup.md) if your deployment fails and/or you need to clean up the resources.     

## For local development & debugging

Follow steps in [Local Debugging Setup](./LocalDebuggingSetup.md) to configure your local development environment for debugging the solution.

## Sample Questions

To help you get started, here are some [Sample Questions](./SampleQuestions.md) you can follow to try it out.

## Next Steps: 
Now that you've completed your deployment, you can start using the solution. Try out these things to start getting familiar with the capabilities:
* [Customize the solution](./CustomizeData.md) with your own data
