# Customizing azd Parameters

You can customize the deployment by setting `azd` environment variables before running `azd up`. These values are resolved into [infra/main.parameters.json](../infra/main.parameters.json) at provision time.

## How to Set a Parameter

```shell
azd env set <PARAMETER_NAME> <value>
```

After setting parameters, run `azd up` (or `azd provision`) to apply them.

## Available Parameters

| Parameter | azd Environment Variable | Default | Description |
|-----------|--------------------------|---------|-------------|
| `environmentName` | `AZURE_ENV_NAME` | *(prompted)* | Name of the environment; used to derive resource names (3-16 chars, alphanumeric). |
| `location` | `AZURE_LOCATION` | *(prompted)* | Primary Azure region for infrastructure resources. |
| `contentUnderstandingLocation` | `AZURE_CU_LOCATION` | `swedencentral` | Region for the Azure AI Content Understanding resource. |
| `azureAdTenantId` | `AZURE_AD_TENANT_ID` | *(empty)* | Microsoft Entra tenant ID for App Service authentication. |
| `azureAdClientId` | `AZURE_AD_CLIENT_ID` | *(empty)* | App registration client ID for App Service authentication. |
| `useExistingAiProject` | `USE_EXISTING_AI_PROJECT` | `false` | Set to `true` to reuse an existing Azure AI Foundry project. |
| `existingAiFoundryServiceName` | `EXISTING_AI_FOUNDRY_SERVICE_NAME` | *(empty)* | Name of an existing AI Foundry service to reuse. |
| `existingAiFoundryProjectName` | `EXISTING_AI_FOUNDRY_PROJECT_NAME` | *(empty)* | Name of an existing AI Foundry project to reuse. |
| `existingAiFoundryEndpoint` | `EXISTING_AI_FOUNDRY_ENDPOINT` | *(empty)* | Endpoint of an existing AI Foundry project to reuse. |
| `existingAiSearchConnectionName` | `EXISTING_AI_SEARCH_CONNECTION_NAME` | *(empty)* | Name of an existing Azure AI Search connection to reuse. |
| `adminApiKey` | `ADMIN_API_KEY` | *(empty)* | Optional admin API key for privileged operations. |

## Model Configuration

The AI model deployments are defined as parameters in [infra/main.bicep](../infra/main.bicep) with the following defaults for this solution. To change them, edit the defaults in `main.bicep` (they are not mapped as `azd` environment variables):

| Bicep Parameter | Default | Description |
|-----------------|---------|-------------|
| `chatDeploymentName` | `gpt-5.2` | Azure OpenAI chat deployment (also used for insights generation). Deployed at 150k capacity on `GlobalStandard`. |
| `embeddingDeploymentName` | `text-embedding-3-small` | Azure OpenAI embedding deployment for hybrid search. Deployed at 80k capacity on `GlobalStandard`. |
| `gptModelVersion` | `2025-12-11` | Version of the chat model. |
| `deployCosmos` | `false` | Set to `true` to also deploy Cosmos DB (SQL is the primary database; not required). |

## Examples

**Deploy to East US 2 with a specific environment name:**

```shell
azd env set AZURE_ENV_NAME kmdev
azd env set AZURE_LOCATION eastus2
azd up
```

**Reuse an existing Azure AI Foundry project:**

```shell
azd env set USE_EXISTING_AI_PROJECT true
azd env set EXISTING_AI_FOUNDRY_SERVICE_NAME my-foundry-service
azd env set EXISTING_AI_FOUNDRY_PROJECT_NAME my-foundry-project
azd env set EXISTING_AI_FOUNDRY_ENDPOINT https://my-foundry.services.ai.azure.com/
azd up
```

**Set the Content Understanding region:**

```shell
azd env set AZURE_CU_LOCATION westus
azd up
```

## Viewing Current Values

```shell
azd env get-values
```

## Next Steps

Return to the [Deployment Guide](./DeploymentGuide.md#32-advanced-configuration-optional) to continue.
