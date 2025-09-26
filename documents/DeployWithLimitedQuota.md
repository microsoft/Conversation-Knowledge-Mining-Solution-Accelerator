# Deploying with Limited OpenAI Quota

This document provides guidance on deploying the Conversation Knowledge Solution Accelerator when you have limited Azure OpenAI model quota available.

## Overview

By default, the solution requires:
- **GPT model**: 150,000 Tokens Per Minute (TPM)
- **Embedding model**: 80,000 TPM

If your Azure OpenAI service has lower quota limits, you can modify the deployment to work with reduced capacity.

## Prerequisites

Before proceeding, ensure you have:
- Azure Developer CLI (azd) installed
- Access to your Azure OpenAI service quota settings
- Knowledge of your current TPM limits

## Deployment Options

You have two approaches to deploy with less quota:

### Option 1: Remove Quota Validation

Remove the metadata section (lines 34-42) from the [`infra/main.bicep`](../infra/main.bicep) file:

```bicep
@metadata({
  azd: {
    type: 'location'
    usageName: [
      'OpenAI.GlobalStandard.gpt-4o-mini,150'
      'OpenAI.GlobalStandard.text-embedding-ada-002,80'
    ]
  }
})
```

### Option 2: Modify Quota Thresholds (Recommended)

Update the values on lines 38-39 in [`infra/main.bicep`](../infra/main.bicep) to match your available quota:

```bicep
@metadata({
  azd: {
    type: 'location'
    usageName: [
        'OpenAI.GlobalStandard.gpt4.1, 50'           // Changed from 150
        'OpenAI.GlobalStandard.text-embedding-ada-002, 50'  // Changed from 80
    ]
  }
})
```

## Configuration Steps

After modifying the Bicep file, configure your deployment capacity:

```powershell
azd env set AZURE_OPENAI_DEPLOYMENT_MODEL_CAPACITY="50"
azd env set AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY="50"
```

> **Note**: Adjust the values (50) to match your actual available quota.

## Deploy the Solution

Once configured, proceed with deployment:

```powershell
azd up
```

## Performance Considerations

⚠️ **Important**: Using reduced TPM limits may impact application performance:

For optimal performance, we recommend maintaining at least 150,000 TPM for GPT models when possible.

## Additional Resources

For more detailed information, refer to:

- [Deployment Guide](DeploymentGuide.md) - Complete deployment instructions
- [Customizing azd Parameters](CustomizingAzdParameters.md) - Advanced configuration options
- [Check or update Quota](AzureGPTQuotaSettings.md) - Check or update quota from Azure Portal
- [Quota Check](QuotaCheck.md) - Script for checking Azure OpenAI quota limits

## Why we need to do this?
- The solution uses built-in Azure Developer CLI (azd) quota validation to prevent deployment failures. Specifically, azd performs pre-deployment checks to ensure sufficient quota is available i.e. 150k TPM for gpt model and 80k TPM for embedding model.

- These quota thresholds are hardcoded in the infrastructure file because azd's quota checking mechanism doesn't currently support parameterized values. If your Azure OpenAI service has quota below these thresholds, the deployment will fail during the validation phase rather than proceeding and failing later in the process.

- By following the steps above, you can either:
    1. **Bypass quota validation entirely** by removing the metadata block
    2. **Lower the validation thresholds** to match your available quota (e.g., 50,000 TPM)

- This ensures successful deployment while working within your quota constraints.