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
| `deploymentFlavor` | `DEPLOYMENT_FLAVOR` | `bicep` | Infrastructure variant: `bicep`, `avm`, or `avm-waf`. See [Deployment Flavor & Production (WAF) Parameters](#deployment-flavor--production-waf-parameters). |
| `azureAiServiceLocation` | `AZURE_ENV_AI_SERVICE_LOCATION` | *(location)* | Region for the Azure AI (OpenAI) service. |
| `appServicePlanSku` | `AZURE_ENV_APP_SERVICE_PLAN_SKU` | `B3` | App Service Plan SKU for the backend and frontend web apps. |
| `containerRegistryName` | `AZURE_ENV_CONTAINER_REGISTRY_NAME` | *(generated)* | Name of an existing Azure Container Registry to reuse (leave empty to create one). |
| `backendContainerImageTag` / `frontendContainerImageTag` | `AZURE_ENV_IMAGE_TAG` | `latest` | Container image tag to deploy. |
| `deployCosmos` | `AZURE_ENV_DEPLOY_COSMOS` | `false` | Deploy Cosmos DB alongside SQL (SQL is the primary database; not required). |
| `existingLogAnalyticsWorkspaceId` | `AZURE_ENV_EXISTING_LOG_ANALYTICS_WORKSPACE_RID` | *(empty)* | Resource ID of an existing Log Analytics workspace to reuse. |
| `existingFoundryProjectResourceId` | `AZURE_EXISTING_AIPROJECT_RESOURCE_ID` | *(empty)* | Resource ID of an existing Azure AI Foundry project to reuse. |
| `deployingUserPrincipalType` | `DEPLOYING_USER_PRINCIPAL_TYPE` | `User` | Principal type of the deployer (`User` or `ServicePrincipal`); used for data-plane RBAC assignments. |

## Model Configuration

The AI model deployments are defined as parameters in [infra/main.bicep](../infra/main.bicep) with the following defaults for this solution. To change them, edit the defaults in `main.bicep` (they are not mapped as `azd` environment variables):

| Bicep Parameter | Default | Description |
|-----------------|---------|-------------|
| `chatDeploymentName` | `gpt-5.2` | Azure OpenAI chat deployment (also used for insights generation). Deployed at 150k capacity on `GlobalStandard`. |
| `embeddingDeploymentName` | `text-embedding-3-small` | Azure OpenAI embedding deployment for hybrid search. Deployed at 80k capacity on `GlobalStandard`. |
| `gptModelVersion` | `2025-12-11` | Version of the chat model. |
| `deployCosmos` | `false` | Set to `true` to also deploy Cosmos DB (SQL is the primary database; not required). |

## Deployment Flavor & Production (WAF) Parameters

The infrastructure supports three deployment flavors, selected by the `deploymentFlavor` value in [infra/main.parameters.json](../infra/main.parameters.json):

| Flavor | Description |
|--------|-------------|
| `bicep` | **Default.** Development / testing deployment without private networking. |
| `avm` | Azure Verified Modules without private networking. |
| `avm-waf` | Well-Architected Framework aligned: private networking, VNet, private endpoints, jumpbox VM + Bastion, and optional redundancy. |

**How to select a flavor:** the deployment flavor is chosen by which parameters file is active — `azd` always reads `infra/main.parameters.json`. To deploy the Production (WAF) flavor, copy the WAF parameters file over the default:

```powershell
Copy-Item ./infra/main.waf.parameters.json ./infra/main.parameters.json -Force
```

```bash
cp ./infra/main.waf.parameters.json ./infra/main.parameters.json
```

The WAF parameters file sets the following additional values. Flags without an `azd` environment variable are hard-coded in the file — edit the file directly to change them.

| Parameter | azd Environment Variable | Default (WAF file) | Description |
|-----------|--------------------------|--------------------|-------------|
| `deploymentFlavor` | `DEPLOYMENT_FLAVOR` | `avm-waf` | Selects the WAF infrastructure variant. |
| `enableMonitoring` | *(hard-coded)* | `true` | Application Insights + Log Analytics. |
| `enablePrivateNetworking` | *(hard-coded)* | `true` | VNet, private endpoints, jumpbox VM, and Azure Bastion. |
| `enableScalability` | *(hard-coded)* | `true` | Higher SKUs and autoscale settings. |
| `enableRedundancy` | *(hard-coded)* | `false` | Zone redundancy and Log Analytics workspace replication. |
| `enableTelemetry` | `AZURE_ENV_ENABLE_TELEMETRY` | `true` | Anonymous deployment telemetry. |
| `vmAdminUsername` | `AZURE_ENV_VM_ADMIN_USERNAME` | *(empty)* | Jumpbox admin username (fallback; login is via Entra ID + Bastion). |
| `vmAdminPassword` | `AZURE_ENV_VM_ADMIN_PASSWORD` | *(empty)* | Jumpbox admin password. |
| `vmSize` | `AZURE_ENV_VM_SIZE` | `Standard_D2s_v5` | Jumpbox VM size. |

> **Production prerequisite:** the WAF jumpbox VM enables host encryption, so the `EncryptionAtHost` feature must be registered on the subscription before deploying. See [Choose Deployment Type](./DeploymentGuide.md#33-choose-deployment-type-standard-vs-production) for the registration commands and VM credential setup.

## Examples

**Deploy to Australia East with a specific environment name:**

```shell
azd env set AZURE_ENV_NAME kmdev
azd env set AZURE_LOCATION australiaeast
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
azd env set AZURE_CU_LOCATION swedencentral
azd up
```

**Deploy the Production (WAF) configuration with VM credentials:**

```shell
Copy-Item ./infra/main.waf.parameters.json ./infra/main.parameters.json -Force
azd env set AZURE_ENV_VM_ADMIN_USERNAME azureadmin
azd env set AZURE_ENV_VM_ADMIN_PASSWORD <strong-password>
azd up
```

## Viewing Current Values

```shell
azd env get-values
```

## Next Steps

Return to the [Deployment Guide](./DeploymentGuide.md#32-advanced-configuration-optional) to continue.
