targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (e.g., dev, prod)')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Name of the Azure OpenAI chat deployment')
param chatDeploymentName string = 'gpt-4o'

@description('Name of the Azure OpenAI embedding deployment')
param embeddingDeploymentName string = 'text-embedding-ada-002'

@description('GPT model version')
param gptModelVersion string = '2024-11-20'

@description('Azure AD tenant ID for authentication')
param azureAdTenantId string = ''

@description('Azure AD client ID for authentication')
param azureAdClientId string = ''

// ── Existing AI Foundry Project (optional) ──
@description('Set to true to reuse an existing Azure AI Foundry project instead of creating new AI resources')
param useExistingAiProject bool = false

@description('Name of the existing AI Services account (parent of the project)')
param existingAiFoundryServiceName string = ''

@description('Name of the existing AI Foundry project')
param existingAiFoundryProjectName string = ''

@description('Endpoint of the existing AI Foundry AI Services (for OpenAI + CU)')
param existingAiFoundryEndpoint string = ''

@description('Name of the AI Search connection in the existing AI Foundry project')
param existingAiSearchConnectionName string = ''

var abbrs = loadJsonContent('abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

// Resource Group
resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: '${abbrs.resourceGroup}${environmentName}'
  location: location
  tags: tags
}

// ── AI Foundry
module aiServices 'modules/ai-services.bicep' = if (!useExistingAiProject) {
  name: 'ai-services'
  scope: rg
  params: {
    name: '${abbrs.cognitiveServicesAccount}${resourceToken}'
    location: location
    kind: 'AIServices'
    sku: 'S0'
    customSubDomainName: '${abbrs.cognitiveServicesAccount}${resourceToken}'
    projectName: 'km-project-${resourceToken}'
    projectDescription: 'Knowledge Mining AI Foundry Project'
    publicNetworkAccess: 'Enabled'
    deployments: [
      {
        name: chatDeploymentName
        model: {
          format: 'OpenAI'
          name: chatDeploymentName
          version: gptModelVersion
        }
        sku: {
          name: 'GlobalStandard'
          capacity: 30
        }
      }
      {
        name: embeddingDeploymentName
        model: {
          format: 'OpenAI'
          name: embeddingDeploymentName
          version: '2'
        }
        sku: {
          name: 'Standard'
          capacity: 120
        }
      }
    ]
  }
}

// Azure AI Search
module search 'modules/search.bicep' = {
  name: 'search'
  scope: rg
  params: {
    name: '${abbrs.searchService}${resourceToken}'
    location: location
    tags: tags
  }
}

// use existing or newly created 
var aiServicesEndpoint = useExistingAiProject ? existingAiFoundryEndpoint : aiServices!.outputs.endpoint
var aiServicesName = useExistingAiProject ? existingAiFoundryServiceName : aiServices!.outputs.name

// Azure Storage Account
module storage 'modules/storage.bicep' = {
  name: 'storage'
  scope: rg
  params: {
    name: '${abbrs.storageAccount}${resourceToken}'
    location: location
    tags: tags
  }
}

// Azure SQL Database
module sql 'modules/sql.bicep' = {
  name: 'sql'
  scope: rg
  params: {
    serverName: '${abbrs.sqlServer}${resourceToken}'
    databaseName: 'km-db'
    location: location
    tags: tags
  }
}

// Azure Cosmos DB (optional — only if deployCosmos is true)
@description('Set to true to also deploy Cosmos DB (not required — SQL is the primary database)')
param deployCosmos bool = false

module cosmos 'modules/cosmos.bicep' = if (deployCosmos) {
  name: 'cosmos'
  scope: rg
  params: {
    name: '${abbrs.cosmosDBAccount}${resourceToken}'
    location: location
    tags: tags
    databaseName: 'km-db'
  }
}

// Container Apps Environment
module containerApps 'modules/container-apps.bicep' = {
  name: 'container-apps'
  scope: rg
  params: {
    name: '${abbrs.containerAppsEnvironment}${resourceToken}'
    location: location
    tags: tags
  }
}

// Backend Container App
module backend 'modules/container-app.bicep' = {
  name: 'backend'
  scope: rg
  params: {
    name: '${abbrs.containerApp}backend-${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'backend' })
    containerAppsEnvironmentId: containerApps.outputs.environmentId
    targetPort: 8000
    env: [
      { name: 'AZURE_OPENAI_ENDPOINT', value: aiServicesEndpoint }
      { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT', value: chatDeploymentName }
      { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingDeploymentName }
      { name: 'AZURE_SEARCH_ENDPOINT', value: search.outputs.endpoint }
      { name: 'AZURE_SEARCH_INDEX_NAME', value: 'knowledge-mining-index' }
      { name: 'AZURE_CONTENT_UNDERSTANDING_ENDPOINT', value: aiServicesEndpoint }
      { name: 'AZURE_STORAGE_ACCOUNT', value: storage.outputs.accountName }
      { name: 'AZURE_SQL_SERVER', value: sql.outputs.serverFqdn }
      { name: 'AZURE_SQL_DATABASE', value: 'km-db' }
      { name: 'AZURE_COSMOS_ENDPOINT', value: deployCosmos ? cosmos!.outputs.endpoint : '' }
      { name: 'AZURE_COSMOS_DATABASE', value: deployCosmos ? 'km-db' : '' }
      { name: 'AZURE_AD_TENANT_ID', value: azureAdTenantId }
      { name: 'AZURE_AD_CLIENT_ID', value: azureAdClientId }
      { name: 'AZURE_AI_AGENT_ENDPOINT', value: useExistingAiProject ? existingAiFoundryEndpoint : aiServices!.outputs.aiProjectInfo.apiEndpoint }
      { name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: useExistingAiProject ? existingAiSearchConnectionName : '' }
    ]
  }
}

// Frontend Container App
module frontend 'modules/container-app.bicep' = {
  name: 'frontend'
  scope: rg
  params: {
    name: '${abbrs.containerApp}frontend-${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'frontend' })
    containerAppsEnvironmentId: containerApps.outputs.environmentId
    targetPort: 3000
    env: [
      { name: 'REACT_APP_API_BASE', value: 'https://${backend.outputs.fqdn}/api' }
    ]
  }
}

// Role Assignments
module roles 'modules/roles.bicep' = {
  name: 'roles'
  scope: rg
  params: {
    openaiName: aiServicesName
    searchName: search.outputs.name
    storageName: storage.outputs.accountName
    cosmosName: deployCosmos ? cosmos!.outputs.name : ''
    cuName: aiServicesName
    backendPrincipalId: backend.outputs.principalId
  }
}

// Outputs for azd
output AZURE_OPENAI_ENDPOINT string = aiServicesEndpoint
output AZURE_SEARCH_ENDPOINT string = search.outputs.endpoint
output AZURE_CONTENT_UNDERSTANDING_ENDPOINT string = aiServicesEndpoint
output AZURE_STORAGE_ACCOUNT string = storage.outputs.accountName
output AZURE_SQL_SERVER string = sql.outputs.serverFqdn
output AZURE_SQL_DATABASE string = 'km-db'
output AZURE_COSMOS_ENDPOINT string = deployCosmos ? cosmos!.outputs.endpoint : ''
output AZURE_AI_AGENT_ENDPOINT string = useExistingAiProject ? '${existingAiFoundryEndpoint}/projects/${existingAiFoundryProjectName}' : aiServices!.outputs.aiProjectInfo.apiEndpoint
output SERVICE_BACKEND_URI string = backend.outputs.uri
output SERVICE_FRONTEND_URI string = frontend.outputs.uri
