# AVM Post Deployment Guide

> **📋 Note**: This guide is specifically for post-deployment steps after using the AVM template. For complete deployment instructions, see the main [Deployment Guide](./DeploymentGuide.md).

---

## Overview

This document provides guidance on post-deployment steps after deploying the Conversation Knowledge Mining solution accelerator from the [AVM (Azure Verified Modules) repository](https://github.com/Azure/bicep-registry-modules/tree/main/avm/ptn/sa/conversation-knowledge-mining).

---

## Prerequisites

Before proceeding, ensure you have the following:

### 1. Azure Subscription & Permissions

You need access to an [Azure subscription](https://azure.microsoft.com/free/) with permissions to:
- Create resource groups and resources
- Create app registrations
- Assign roles at the resource group level (Contributor + RBAC)

📖 Follow the steps in [Azure Account Set Up](./AzureAccountSetUp.md) for detailed instructions.

### 2. Deployed Infrastructure

A successful Conversation Knowledge Mining solution accelerator deployment from the [AVM repository](https://github.com/Azure/bicep-registry-modules/tree/main/avm/ptn/sa/conversation-knowledge-mining).

### 3. Required Tools

Ensure the following tools are installed on your machine:

| Tool | Version | Download Link |
|------|---------|---------------|
| PowerShell | v7.0+ | [Install PowerShell](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell?view=powershell-7.5) |
| Azure Developer CLI (azd) | v1.18.0+ | [Install azd](https://aka.ms/install-azd) |
| Python | 3.9+ | [Download Python](https://www.python.org/downloads/) |
| Docker Desktop | Latest | [Download Docker](https://www.docker.com/products/docker-desktop/) |
| Git | Latest | [Download Git](https://git-scm.com/downloads) |
| Microsoft ODBC Driver | 18 | [Download ODBC Driver](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver16) |

---

## Post-Deployment Steps

### Step 1: Clone the Repository

Clone this repository to access the post-deployment scripts and sample data:

```powershell
git clone https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator.git
```

```powershell
cd Conversation-Knowledge-Mining-Solution-Accelerator
```

---

### Step 2: Run the Data Processing Script

#### 2.1 Login to Azure

```shell
az login
```

> 💡 **Tip**: If using VS Code Web, use device code authentication:
> ```shell
> az login --use-device-code
> ```

#### 2.2 Execute the Script

Run the bash script from the output of the AVM deployment:

```bash
bash ./infra/scripts/process_sample_data.sh <Resource-Group-Name>
```

> ⚠️ **Important**: Replace `<Resource-Group-Name>` with your actual resource group name from the deployment.

---

### Step 3: Access the Application

1. Navigate to the [Azure Portal](https://portal.azure.com)
2. Open the **resource group** created during deployment
3. Locate the **App Service** with name starting with `app-`
4. Copy the **URL** from the Overview page
5. Open the URL in your browser to access the application

---

### Step 4: Configure Authentication (Optional)

If you want to enable authentication for your application, follow the [App Authentication Guide](./AppAuthentication.md).

---

### Step 5: Verify Data Processing

Confirm your deployment is working correctly:

| Check | Location |
|-------|----------|
| ✅ Sample data uploaded | Storage Account |
| ✅ AI Search index created and populated | Azure AI Search |
| ✅ Application loads without errors | App Service URL |

---

## Getting Started

### Sample Questions

To help you get started, here are some [Sample Questions](./SampleQuestions.md) you can follow to try it out.

---

## Troubleshooting

If you encounter issues, refer to the [Troubleshooting Guide](./TroubleShootingSteps.md).
