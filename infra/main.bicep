// ============================================================================
// main.bicep — Deployment Router
// Description: Routes deployment to the appropriate infrastructure flavor.
//   - 'bicep'   → Vanilla Bicep modules (Docker deployment)
//   - 'avm'     → AVM-based modules (non-WAF)
//   - 'avm-waf' → AVM-based modules with WAF-aligned features
//              (monitoring, private networking, scalability, redundancy)
// ============================================================================
targetScope = 'resourceGroup'

// ============================================================================
// Routing Parameter
// ============================================================================

@allowed(['bicep', 'avm', 'avm-waf'])
@description('Required. Deployment flavor: bicep (vanilla Docker), avm (AVM non-WAF), or avm-waf (AVM WAF-aligned).')
param deploymentFlavor string

// ============================================================================
// Parameters — Core (shared across all flavors)
// ============================================================================

@minLength(3)
@maxLength(16)
@description('Optional. A unique application/solution name used as base for all resource naming.')
param solutionName string = 'kmgen'

@maxLength(5)
@description('Optional. A unique text suffix appended to resource names for uniqueness.')
param solutionUniqueText string = substring(uniqueString(subscription().id, resourceGroup().name, solutionName), 0, 5)

@metadata({ azd: { type: 'location' } })
@description('Optional. Primary Azure region for resource deployment.')
param location string = resourceGroup().location

@allowed(['australiaeast', 'swedencentral', 'southeastasia'])
@metadata({
  azd:{
    type: 'location'
    usageName: [
      'OpenAI.GlobalStandard.gpt-5.2,150'
      'OpenAI.GlobalStandard.text-embedding-3-small,80'
    ]
  }
})
@description('Required. Location for AI Foundry and model deployments.')
param azureAiServiceLocation string

@description('Optional. Set to true to also deploy Cosmos DB (not required — SQL is the primary database).')
param deployCosmos bool = false

// ============================================================================
// Parameters — AI Configuration
// ============================================================================

@allowed(['Standard', 'GlobalStandard'])
@description('Optional. GPT model deployment type.')
param deploymentType string = 'GlobalStandard'

@description('Optional. Name of the GPT model to deploy.')
param gptModelName string = 'gpt-5.2'

@description('Optional. Version of the GPT model to deploy.')
param gptModelVersion string = '2025-12-11'

@minValue(10)
@description('Optional. Capacity of the GPT deployment (TPM in thousands).')
param gptDeploymentCapacity int = 150

@allowed(['text-embedding-3-small'])
@description('Optional. Name of the Text Embedding model to deploy.')
param embeddingModel string = 'text-embedding-3-small'

@minValue(10)
@description('Optional. Capacity of the Embedding Model deployment.')
param embeddingDeploymentCapacity int = 80

// ============================================================================
// Parameters — Compute
// ============================================================================

@description('Optional. Name of the Azure Container Registry.')
param containerRegistryName string = 'kmcontainerreg'

@description('Optional. Backend container image name.')
param backendContainerImageName string = 'km-api'

@description('Optional. Backend container image tag.')
param backendContainerImageTag string = 'latest'

@description('Optional. Frontend container image name.')
param frontendContainerImageName string = 'km-app'

@description('Optional. Frontend container image tag.')
param frontendContainerImageTag string = 'latest'

@allowed(['F1', 'D1', 'B1', 'B2', 'B3', 'S1', 'S2', 'S3', 'P1', 'P2', 'P3', 'P1v3', 'P1v4'])
@description('Optional. App Service Plan SKU.')
param appServicePlanSku string = 'B3'

@description('Kind of web app.')
param kind string = 'app,linux,container'

// ============================================================================
// Parameters — Authentication (matches infra_old/main.bicep)
// ============================================================================

@description('Optional. Azure AD tenant ID for authentication.')
param azureAdTenantId string = ''

@description('Optional. Azure AD client ID for authentication.')
param azureAdClientId string = ''

@description('Optional. Admin API key for script-based authentication (setup-data, post-deploy scripts). Leave empty to disable.')
@secure()
param adminApiKey string = ''

// ============================================================================
// Parameters — Existing Resources
// ============================================================================

@description('Optional. Resource ID of an existing Log Analytics workspace. Empty creates a new one.')
param existingLogAnalyticsWorkspaceId string = ''

@description('Optional. Resource ID of an existing AI Foundry project. Empty creates a new one.')
param existingFoundryProjectResourceId string = ''

// ============================================================================
// Parameters — Identity
// ============================================================================

@allowed(['User', 'ServicePrincipal'])
@description('Optional. Principal type of the deploying user. Use ServicePrincipal for CI/CD pipelines with OIDC.')
param deployingUserPrincipalType string = 'User'

// ============================================================================
// Parameters — AVM-specific (ignored when deploymentFlavor = 'bicep')
// ============================================================================

@description('Optional. Tags to apply to all resources (AVM only).')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for AVM modules.')
param enableTelemetry bool = true

@description('Optional. Enable monitoring (Log Analytics, App Insights, diagnostic settings).')
param enableMonitoring bool = false

@description('Optional. Enable private networking (VNet, private endpoints, DNS zones).')
param enablePrivateNetworking bool = false

@description('Optional. Enable scalability features (zone redundant App Service Plan).')
param enableScalability bool = false

@description('Optional. Enable redundancy (zone redundant Cosmos DB, multi-region failover).')
param enableRedundancy bool = false

@secure()
@description('Optional. VM admin username (AVM-WAF only, when private networking is enabled).')
param vmAdminUsername string?

@secure()
@description('Optional. VM admin password (AVM-WAF only, when private networking is enabled).')
param vmAdminPassword string?

@description('Optional. VM size for jumpbox (AVM-WAF only). Defaults to Standard_D2s_v5.')
param vmSize string = 'Standard_D2s_v5'

// ============================================================================
// Derived Variables
// ============================================================================

var isAvm = deploymentFlavor == 'avm' || deploymentFlavor == 'avm-waf'
var isBicep = deploymentFlavor == 'bicep'

// ============================================================================
// Module: AVM Deployment (non-WAF and WAF)
// Activated when deploymentFlavor = 'avm' or 'avm-waf'
// WAF features (monitoring, private networking, scalability, redundancy)
// are enabled automatically for 'avm-waf'.
// ============================================================================

module avmDeployment './avm/main.bicep' = if (isAvm) {
  name: take('module.avm.${solutionName}', 64)
  params: {
    solutionName: solutionName
    solutionUniqueText: solutionUniqueText
    location: location
    azureAiServiceLocation: azureAiServiceLocation
    tags: tags
    enableTelemetry: enableTelemetry
    enableMonitoring: enableMonitoring
    enablePrivateNetworking: enablePrivateNetworking
    enableScalability: enableScalability
    enableRedundancy: enableRedundancy
    vmAdminUsername: vmAdminUsername
    vmAdminPassword: vmAdminPassword
    vmSize: vmSize
    deployCosmos: deployCosmos
    deploymentType: deploymentType
    gptModelName: gptModelName
    gptModelVersion: gptModelVersion
    gptDeploymentCapacity: gptDeploymentCapacity
    embeddingModel: embeddingModel
    embeddingDeploymentCapacity: embeddingDeploymentCapacity
    kind: kind
    containerRegistryName: containerRegistryName
    appServicePlanSku: appServicePlanSku
    backendContainerImageName: backendContainerImageName
    backendContainerImageTag: backendContainerImageTag
    frontendContainerImageName: frontendContainerImageName
    frontendContainerImageTag: frontendContainerImageTag
    azureAdTenantId: azureAdTenantId
    azureAdClientId: azureAdClientId
    adminApiKey: adminApiKey
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    deployingUserPrincipalType: deployingUserPrincipalType
  }
}

// ============================================================================
// Module: Vanilla Bicep Deployment (Docker)
// Activated when deploymentFlavor = 'bicep'
// ============================================================================

module bicepDeployment './bicep/main.bicep' = if (isBicep) {
  name: take('module.bicep.${solutionName}', 64)
  params: {
    solutionName: solutionName
    solutionUniqueText: solutionUniqueText
    location: location
    azureAiServiceLocation: azureAiServiceLocation
    tags: tags
    deployCosmos: deployCosmos
    deploymentType: deploymentType  
    gptModelName: gptModelName
    gptModelVersion: gptModelVersion
    gptDeploymentCapacity: gptDeploymentCapacity
    embeddingModel: embeddingModel
    embeddingDeploymentCapacity: embeddingDeploymentCapacity
    kind: kind
    containerRegistryName: containerRegistryName
    appServicePlanSku: appServicePlanSku
    backendContainerImageName: backendContainerImageName
    backendContainerImageTag: backendContainerImageTag
    frontendContainerImageName: frontendContainerImageName
    frontendContainerImageTag: frontendContainerImageTag
    azureAdTenantId: azureAdTenantId
    azureAdClientId: azureAdClientId
    adminApiKey: adminApiKey
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    deployingUserPrincipalType: deployingUserPrincipalType
  }
}

// ============================================================================
// Outputs — Coalesced from whichever flavor was deployed (matches infra_old/main.bicep)
// ============================================================================

@description('Azure OpenAI endpoint URL.')
output AZURE_OPENAI_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_OPENAI_ENDPOINT : bicepDeployment!.outputs.AZURE_OPENAI_ENDPOINT

@description('Azure AI Search endpoint URL.')
output AZURE_SEARCH_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_SEARCH_ENDPOINT : bicepDeployment!.outputs.AZURE_SEARCH_ENDPOINT

@description('Azure Content Understanding endpoint URL.')
output AZURE_CONTENT_UNDERSTANDING_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_CONTENT_UNDERSTANDING_ENDPOINT : bicepDeployment!.outputs.AZURE_CONTENT_UNDERSTANDING_ENDPOINT

@description('Azure Storage account name.')
output AZURE_STORAGE_ACCOUNT string = isAvm ? avmDeployment!.outputs.AZURE_STORAGE_ACCOUNT : bicepDeployment!.outputs.AZURE_STORAGE_ACCOUNT

@description('Azure SQL Server FQDN.')
output AZURE_SQL_SERVER string = isAvm ? avmDeployment!.outputs.AZURE_SQL_SERVER : bicepDeployment!.outputs.AZURE_SQL_SERVER

@description('Azure SQL Database name.')
output AZURE_SQL_DATABASE string = isAvm ? avmDeployment!.outputs.AZURE_SQL_DATABASE : bicepDeployment!.outputs.AZURE_SQL_DATABASE

@description('Backend API application (and SQL contained user) name.')
output API_APP_NAME string = isAvm ? avmDeployment!.outputs.API_APP_NAME : bicepDeployment!.outputs.API_APP_NAME

@description('Backend API system-assigned managed identity principal ID.')
output AZURE_API_PRINCIPAL_ID string = isAvm ? avmDeployment!.outputs.AZURE_API_PRINCIPAL_ID : bicepDeployment!.outputs.AZURE_API_PRINCIPAL_ID

@description('Azure Cosmos DB endpoint.')
output AZURE_COSMOS_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_COSMOS_ENDPOINT : bicepDeployment!.outputs.AZURE_COSMOS_ENDPOINT

@description('Azure AI Agent endpoint URL.')
output AZURE_AI_AGENT_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_AI_AGENT_ENDPOINT : bicepDeployment!.outputs.AZURE_AI_AGENT_ENDPOINT

@description('Backend API application URL.')
output API_APP_URL string = isAvm ? avmDeployment!.outputs.API_APP_URL : bicepDeployment!.outputs.API_APP_URL

@description('Frontend web application URL.')
output WEB_APP_URL string = isAvm ? avmDeployment!.outputs.WEB_APP_URL : bicepDeployment!.outputs.WEB_APP_URL

@description('Backend service URI (used by azd).')
output SERVICE_BACKEND_URI string = isAvm ? avmDeployment!.outputs.SERVICE_BACKEND_URI : bicepDeployment!.outputs.SERVICE_BACKEND_URI

@description('Frontend service URI (used by azd).')
output SERVICE_FRONTEND_URI string = isAvm ? avmDeployment!.outputs.SERVICE_FRONTEND_URI : bicepDeployment!.outputs.SERVICE_FRONTEND_URI

@description('AI Search connection name in AI Foundry.')
output AZURE_AI_SEARCH_CONNECTION_NAME string = isAvm ? avmDeployment!.outputs.AZURE_AI_SEARCH_CONNECTION_NAME : bicepDeployment!.outputs.AZURE_AI_SEARCH_CONNECTION_NAME

@description('Azure Container Registry name.')
output ACR_NAME string = isAvm ? avmDeployment!.outputs.ACR_NAME : bicepDeployment!.outputs.ACR_NAME

@description('Azure Container Registry login server URL.')
output ACR_LOGIN_SERVER string = isAvm ? avmDeployment!.outputs.ACR_LOGIN_SERVER : bicepDeployment!.outputs.ACR_LOGIN_SERVER

@description('Backend container image repository name to build and push to ACR.')
output BACKEND_CONTAINER_IMAGE_NAME string = isAvm ? avmDeployment!.outputs.BACKEND_CONTAINER_IMAGE_NAME : bicepDeployment!.outputs.BACKEND_CONTAINER_IMAGE_NAME

@description('Backend container image tag to build and push to ACR.')
output BACKEND_CONTAINER_IMAGE_TAG string = isAvm ? avmDeployment!.outputs.BACKEND_CONTAINER_IMAGE_TAG : bicepDeployment!.outputs.BACKEND_CONTAINER_IMAGE_TAG

@description('Frontend container image repository name to build and push to ACR.')
output FRONTEND_CONTAINER_IMAGE_NAME string = isAvm ? avmDeployment!.outputs.FRONTEND_CONTAINER_IMAGE_NAME : bicepDeployment!.outputs.FRONTEND_CONTAINER_IMAGE_NAME

@description('Frontend container image tag to build and push to ACR.')
output FRONTEND_CONTAINER_IMAGE_TAG string = isAvm ? avmDeployment!.outputs.FRONTEND_CONTAINER_IMAGE_TAG : bicepDeployment!.outputs.FRONTEND_CONTAINER_IMAGE_TAG

@description('Frontend web application (App Service) name.')
output FRONTEND_APP_NAME string = isAvm ? avmDeployment!.outputs.FRONTEND_APP_NAME : bicepDeployment!.outputs.FRONTEND_APP_NAME

@description('Resource group name.')
output RESOURCE_GROUP_NAME string = resourceGroup().name

@description('Solution resource token suffix used in resource names.')
output SOLUTION_SUFFIX string = isAvm ? avmDeployment!.outputs.SOLUTION_SUFFIX : bicepDeployment!.outputs.SOLUTION_SUFFIX

@description('Whether the deployment uses private endpoints. Post-provision scripts gate ACR admin-credential image pull on this.')
output ENABLE_PRIVATE_NETWORKING bool = enablePrivateNetworking
