// ========== main.bicep ========== //

// ============================================================================
// main.bicep — Orchestrator
// Description: Pure orchestrator for Conversation Knowledge Mining solution. Calls modules to deploy resources.
//              All resource names are derived from params — no hardcoded names.
//              This file only calls modules; no inline resource definitions.
// ============================================================================

targetScope = 'resourceGroup'

// ============================================================================
// Parameters — Core
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

@description('Optional. Tags to apply to all resources.')
param tags object = {}

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

@description('Optional. Name of the Azure Container Registry. Leave empty to auto-generate a globally unique name (cr<suffix>).')
param containerRegistryName string = ''

@description('Optional. Backend container image name.')
param backendContainerImageName string = 'km-api'

@description('Optional. Backend container image tag.')
param backendContainerImageTag string = 'latest'

@description('Optional. Frontend container image name.')
param frontendContainerImageName string = 'km-app'

@description('Optional. Frontend container image tag.')
param frontendContainerImageTag string = 'latest'

@allowed(['F1', 'D1', 'B1', 'B2', 'B3', 'S1', 'S2', 'S3', 'P1', 'P2', 'P3', 'P1v3', 'P1v4'])
@description('Optional. App Service Plan SKU (used by AVM flavors).')
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

@description('Optional. Created by user name for resource tagging.')
param createdBy string = contains(deployer(), 'userPrincipalName') ? split(deployer().userPrincipalName, '@')[0] : deployer().objectId

// ============================================================================
// Variables
// ============================================================================

var solutionSuffix = toLower(trim(replace(
  replace(
    replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''),
    ' ',
    ''
  ),
  '*',
  ''
)))

// ACR names are globally unique — default to a suffixed name so multiple deployments don't collide.
var containerRegistryResourceName = !empty(containerRegistryName) ? containerRegistryName : 'acrkm${solutionSuffix}'

var deployerInfo = deployer()
var deployingUserPrincipalId = deployerInfo.objectId
var deployingUserPrincipalName = deployerInfo.?userPrincipalName ?? deployerInfo.objectId
var existingTags = resourceGroup().tags ?? {}


// Tags: merge existing RG tags with standard metadata
var resourceTags = union(existingTags, tags, {
  TemplateName: 'KM-Generic'
  CreatedBy: createdBy
  DeploymentName: deployment().name
  Type: 'Non-WAF'
})

// ============================================================================
// Resource Group Tags
// ============================================================================
resource resourceGroupTags 'Microsoft.Resources/tags@2024-11-01' = {
  name: 'default'
  properties: {
    tags: resourceTags
  }
}

// ========== Monitoring (Log Analytics + Application Insights) ========== //
var useExistingLogAnalytics = !empty(existingLogAnalyticsWorkspaceId)

// ========== Log Analytics module ========== //
module log_analytics './modules/monitoring/log-analytics.bicep' = if (!useExistingLogAnalytics) {
  name: take('module.log-analytics.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
  }
  scope: resourceGroup(resourceGroup().name)
}

var logAnalyticsWorkspaceResourceId = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspaceId
  : log_analytics!.outputs.resourceId

// ========== Application Insights module ========== //
module app_insights './modules/monitoring/app-insights.bicep' = {
  name: take('module.app-insights.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    workspaceResourceId: logAnalyticsWorkspaceResourceId
  }
  scope: resourceGroup(resourceGroup().name)
}

// ==========AI Foundry and related resources ========== //
var aiModelDeployments = [
  {
    name: gptModelName
    model: gptModelName
    sku: {
      name: deploymentType
      capacity: gptDeploymentCapacity
    }
    version: gptModelVersion
    raiPolicyName: 'Microsoft.Default'
  }
  {
    name: embeddingModel
    model: embeddingModel
    sku: {
      name: 'GlobalStandard'
      capacity: embeddingDeploymentCapacity
    }
    version: '1'
    raiPolicyName: 'Microsoft.Default'
  }
]

// Deploy new AI Services account + AI Foundry project (no connections, no deployments)
module ai_foundry_project './modules/ai/ai-foundry-project.bicep' = if (empty(existingFoundryProjectResourceId)) {
  name: take('module.ai-foundry-project.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: azureAiServiceLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Unified AI Foundry resource name vars ========== //
var useExistingAIProject = !empty(existingFoundryProjectResourceId)
var aiFoundryResourceName = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[8] : ai_foundry_project!.outputs.name
var aiProjectResourceName = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[10] : ai_foundry_project!.outputs.projectName
var aiFoundrySubscriptionId = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[2] : subscription().subscriptionId
var aiFoundryResourceGroupName = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[4] : resourceGroup().name

// Reference existing AI Foundry project (reads runtime properties: endpoints, identities)
module existing_project_setup './modules/ai/existing-project-setup.bicep' = if (useExistingAIProject) {
  name: take('module.existing-project-setup.${solutionName}', 64)
  scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
  params: {
    name: aiFoundryResourceName
    projectName: aiProjectResourceName
  }
}

// AI Search connection (single call for both existing and new paths)
module foundry_search_connection './modules/ai/ai-foundry-connection.bicep' = {
  name: take('module.foundry-search-conn.${solutionName}', 64)
  scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
  params: {
    solutionName: solutionSuffix
    aiServicesAccountName: aiFoundryResourceName
    projectName: aiProjectResourceName
    category: 'CognitiveSearch'
    target: ai_search!.outputs.endpoint
    authType: 'AAD'
    metadata: {
      ApiType: 'Azure'
      ResourceId: ai_search!.outputs.resourceId
    }
  }
}

// Model deployments (single loop for both existing and new paths)
@batchSize(1)
module model_deployments './modules/ai/ai-foundry-model-deployment.bicep' = [for (deployment, i) in aiModelDeployments: {
  name: take('module.model-deployment-${i}.${solutionName}', 64)
  scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
  params: {
    aiServicesAccountName: aiFoundryResourceName
    deploymentName: deployment.name
    modelName: deployment.model
    modelVersion: deployment.version
    raiPolicyName: deployment.raiPolicyName
    skuName: deployment.sku.name
    skuCapacity: deployment.sku.capacity
  }
}]

// ========== AI Search module ========== //
module ai_search './modules/ai/ai-search.bicep' = {
  name: take('module.ai-search.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    skuName: 'standard'
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== AI outputs (ternary: existing vs new) ========== //
var aiFoundryEndpoint = useExistingAIProject ? existing_project_setup!.outputs.endpoint : ai_foundry_project!.outputs.endpoint
var azureOpenAiCuEndpoint = useExistingAIProject ? existing_project_setup!.outputs.azureOpenAiCuEndpoint : ai_foundry_project!.outputs.azureOpenAiCuEndpoint
var projectEndpoint = useExistingAIProject ? existing_project_setup!.outputs.projectEndpoint : ai_foundry_project!.outputs.projectEndpoint
var aiFoundryResourceId = useExistingAIProject ? existing_project_setup!.outputs.resourceId : ai_foundry_project!.outputs.resourceId
var aiProjectPrincipalId = useExistingAIProject ? existing_project_setup!.outputs.projectIdentityPrincipalId : ai_foundry_project!.outputs.projectIdentityPrincipalId

// ========== Storage Account module ========== //
module storage_account './modules/data/storage-account.bicep' = {
  name: take('module.storage-account.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: {}
    containers: [
      { name: 'data', publicAccess: 'None' }
    ]
    enableHierarchicalNamespace: true
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Cosmos DB module (optional — not required, SQL is the primary database) ========== //
module cosmosDBModule './modules/data/cosmos-db-nosql.bicep' = if (deployCosmos) {
  name: take('module.cosmos-db-nosql.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    name: 'cosmos-${solutionSuffix}'
    location: location
    databaseName: 'km-db'
    containers: [
      { name: 'chat_sessions', partitionKeyPath: '/user_id' }
      { name: 'chat_messages', partitionKeyPath: '/session_id' }
      { name: 'document_insights', partitionKeyPath: '/dataset_id' }
      { name: 'enrichment_cache', partitionKeyPath: '/doc_hash' }
    ]
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== SQL Database module ========== //
module sqlDBModule './modules/data/sql-database.bicep' = {
  name: take('module.sql-db.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    name: 'sql-${solutionSuffix}'
    databaseName: 'sqldb-${solutionSuffix}'
    location: location
    tags: resourceTags
    deployerPrincipalId: deployingUserPrincipalId
    deployerPrincipalName: deployingUserPrincipalName
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== App Service Plan module ========== //
module hostingplan './modules/compute/app-service-plan.bicep' = {
  name: take('module.app-service-plan.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    skuName: appServicePlanSku
  }
}

// ========== Container Registry module (dedicated ACR for application images) ========== //
module container_registry './modules/compute/container-registry.bicep' = {
  name: take('module.container-registry.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    name: containerRegistryResourceName
    location: location
    tags: resourceTags
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Compute image names ========== //
var placeholderImageName = 'DOCKER|mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

// ========== Backend Deployment ========== //
module backend_docker './modules/compute/app-service.bicep' = {
  name: take('module.app-service-backend.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    name: 'api-${solutionSuffix}'
    location: location
    tags: union(tags, { 'azd-service-name': 'api' })
    serverFarmResourceId: hostingplan!.outputs.resourceId
    kind: kind
    linuxFxVersion: placeholderImageName
    acrUseManagedIdentityCreds: true
    appSettings: {
      DOCKER_REGISTRY_SERVER_URL: 'https://${container_registry.outputs.loginServer}'
      WEBSITES_PORT: '8000'
      AZURE_OPENAI_ENDPOINT: aiFoundryEndpoint
      AZURE_OPENAI_CHAT_DEPLOYMENT: gptModelName
      AZURE_OPENAI_EMBEDDING_DEPLOYMENT: embeddingModel
      AZURE_SEARCH_ENDPOINT: ai_search.outputs.endpoint
      AZURE_SEARCH_INDEX_NAME: 'knowledge-mining-index'
      AZURE_CONTENT_UNDERSTANDING_ENDPOINT: azureOpenAiCuEndpoint
      AZURE_STORAGE_ACCOUNT: storage_account.outputs.name
      AZURE_SQL_SERVER: sqlDBModule!.outputs.serverFqdn
      AZURE_SQL_DATABASE: sqlDBModule!.outputs.databaseName
      AZURE_COSMOS_ENDPOINT: deployCosmos ? cosmosDBModule!.outputs.endpoint : ''
      AZURE_COSMOS_DATABASE: deployCosmos ? 'km-db' : ''
      AZURE_AD_TENANT_ID: azureAdTenantId
      AZURE_AD_CLIENT_ID: azureAdClientId
      AZURE_AI_AGENT_ENDPOINT: projectEndpoint
      AZURE_AI_SEARCH_CONNECTION_NAME: foundry_search_connection.outputs.connectionName
      API_APP_NAME: 'api-${solutionSuffix}'
      APP_FRONTEND_HOSTNAME: 'https://app-${solutionSuffix}.azurewebsites.net'
      APP_ENV: 'Prod'
      ADMIN_API_KEY: adminApiKey
      SOLUTION_SUFFIX: solutionSuffix
    }
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Frontend Deployment ========== //
module frontend_docker './modules/compute/app-service.bicep' = {
  name: take('module.app-service-frontend.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    name: 'app-${solutionSuffix}'
    location: location
    tags: union(tags, { 'azd-service-name': 'webapp' })
    serverFarmResourceId: hostingplan!.outputs.resourceId
    kind: kind
    linuxFxVersion: placeholderImageName
    acrUseManagedIdentityCreds: true
    appSettings: {
      DOCKER_REGISTRY_SERVER_URL: 'https://${container_registry.outputs.loginServer}'
      APP_API_BASE_URL: backend_docker!.outputs.appUrl
      WEBSITES_PORT: '80'
    }
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Role Assignments (centralized)  ========== //
module role_assignments './modules/identity/role-assignments.bicep' = {
  name: take('module.role-assignments.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    useExistingAIProject: useExistingAIProject
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    aiFoundryResourceId: !useExistingAIProject ? aiFoundryResourceId : ''
    aiSearchResourceId: ai_search.outputs.resourceId
    storageAccountResourceId: storage_account.outputs.resourceId
    aiProjectPrincipalId: aiProjectPrincipalId
    aiSearchPrincipalId: ai_search.outputs.identityPrincipalId
    deployerPrincipalId: deployingUserPrincipalId
    deployerPrincipalType: deployingUserPrincipalType
    backendAppServicePrincipalId: backend_docker!.outputs.identityPrincipalId
    cosmosDbAccountName: deployCosmos ? cosmosDBModule!.outputs.name : ''
    containerRegistryResourceId: container_registry.outputs.resourceId
    acrPullPrincipals: [
      { principalId: backend_docker!.outputs.identityPrincipalId, principalType: 'ServicePrincipal' }
      { principalId: frontend_docker!.outputs.identityPrincipalId, principalType: 'ServicePrincipal' }
    ]
  }
  scope: resourceGroup(resourceGroup().name)
}

 // ========== Outputs (matches infra_old/main.bicep output list) ========== //

@description('Azure OpenAI endpoint URL.')
output AZURE_OPENAI_ENDPOINT string = aiFoundryEndpoint

@description('Azure AI Search endpoint URL.')
output AZURE_SEARCH_ENDPOINT string = ai_search.outputs.endpoint

@description('Azure Content Understanding endpoint URL.')
output AZURE_CONTENT_UNDERSTANDING_ENDPOINT string = azureOpenAiCuEndpoint

@description('Azure Storage account name.')
output AZURE_STORAGE_ACCOUNT string = storage_account.outputs.name

@description('Azure SQL Server FQDN.')
output AZURE_SQL_SERVER string = sqlDBModule!.outputs.serverFqdn

@description('Azure SQL Database name.')
output AZURE_SQL_DATABASE string = sqlDBModule!.outputs.databaseName

@description('Backend API application (and SQL contained user) name.')
output API_APP_NAME string = backend_docker!.outputs.name

@description('Backend API system-assigned managed identity principal ID.')
output AZURE_API_PRINCIPAL_ID string = backend_docker!.outputs.identityPrincipalId

@description('Azure Cosmos DB endpoint.')
output AZURE_COSMOS_ENDPOINT string = deployCosmos ? cosmosDBModule!.outputs.endpoint : ''

@description('Azure AI Agent endpoint URL.')
output AZURE_AI_AGENT_ENDPOINT string = projectEndpoint

@description('Backend API application URL.')
output API_APP_URL string = backend_docker!.outputs.appUrl

@description('Frontend web application URL.')
output WEB_APP_URL string = frontend_docker!.outputs.appUrl

@description('Backend service URI (used by azd).')
output SERVICE_BACKEND_URI string = backend_docker!.outputs.appUrl

@description('Frontend service URI (used by azd).')
output SERVICE_FRONTEND_URI string = frontend_docker!.outputs.appUrl

@description('AI Search connection name in AI Foundry.')
output AZURE_AI_SEARCH_CONNECTION_NAME string = foundry_search_connection.outputs.connectionName

@description('Azure Container Registry name.')
output ACR_NAME string = container_registry.outputs.name

@description('Azure Container Registry login server URL.')
output ACR_LOGIN_SERVER string = container_registry.outputs.loginServer

@description('Backend container image repository name to build and push to ACR.')
output BACKEND_CONTAINER_IMAGE_NAME string = backendContainerImageName

@description('Backend container image tag to build and push to ACR.')
output BACKEND_CONTAINER_IMAGE_TAG string = backendContainerImageTag

@description('Frontend container image repository name to build and push to ACR.')
output FRONTEND_CONTAINER_IMAGE_NAME string = frontendContainerImageName

@description('Frontend container image tag to build and push to ACR.')
output FRONTEND_CONTAINER_IMAGE_TAG string = frontendContainerImageTag

@description('Frontend web application (App Service) name.')
output FRONTEND_APP_NAME string = frontend_docker!.outputs.name

@description('Resource group name.')
output RESOURCE_GROUP_NAME string = resourceGroup().name

@description('Solution resource token suffix used in resource names.')
output SOLUTION_SUFFIX string = solutionSuffix
