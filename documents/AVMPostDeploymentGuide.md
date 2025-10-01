# AVM Post Deployment Guide

> **📋 Note**: This guide is specifically for post-deployment steps after using the AVM template. For complete deployment instructions, see the main [Deployment Guide](./DeploymentGuide.md).

---

This document provides guidance on post-deployment steps after deploying the Conversation Knowledge Mining solution accelerator from the [AVM (Azure Verified Modules) repository](https://github.com/Azure/bicep-registry-modules/tree/main/avm/ptn/sa/conversation-knowledge-mining).

## Prerequisites

- **Deployed Infrastructure** - A successful Conversation Knowledge Mining solution accelerator deployment from the [AVM repository](https://github.com/Azure/bicep-registry-modules/tree/main/avm/ptn/sa/conversation-knowledge-mining)

## Post Deployment Steps

### 1. Access the Application

1. Navigate to the [Azure Portal](https://portal.azure.com)
2. Open the resource group created during deployment
3. Locate the App Service with name starting with `app-`
4. Copy the **URL** from the Overview page
5. Open the URL in your browser to access the application

### 2. Configure Authentication (Optional)

If you want to enable authentication, configure it by following the [App Authentication Guide](./AppAuthentication.md).

### 3. Verify Data Processing

- Check that sample data has been uploaded to the storage account
- Verify that the AI Search index has been created and populated
- Confirm that the application loads without errors

## Getting Started

### Sample Questions

Try these questions in the application to explore the solution capabilities:

- "Total number of calls by date for the last 7 days"
- "Show average handling time by topics in minutes"
- "What are the top 7 challenges users reported?"
- "Give a summary of billing issues"
- "When customers call in about unexpected charges, what types of charges are they seeing?"
