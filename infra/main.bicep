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

@description('Set to true to also deploy Cosmos DB (not required — SQL is the primary database)')
param deployCosmos bool = false

@description('Location for Content Understanding service (must support CU preview API)')
@allowed([
  'swedencentral'
  'australiaeast'
])
param contentUnderstandingLocation string = 'swedencentral'

// ── Container Image Configuration ──
@description('Container registry hostname for backend image')
param backendContainerRegistryHostname string = ''

@description('Backend container image name')
param backendContainerImageName string = 'km-api'

@description('Backend container image tag')
param backendContainerImageTag string = 'latest'

@description('Container registry hostname for frontend image')
param frontendContainerRegistryHostname string = ''

@description('Frontend container image name')
param frontendContainerImageName string = 'km-app'

@description('Frontend container image tag')
param frontendContainerImageTag string = 'latest'

var abbrs = loadJsonContent('abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

// ========== Resource Group ========== //
resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: '${abbrs.managementGovernance.resourceGroup}${environmentName}'
  location: location
  tags: tags
}

// ========== AI Foundry: AI Services ========== //
module aiServices 'modules/ai-services.bicep' = if (!useExistingAiProject) {
  name: 'ai-services'
  scope: rg
  params: {
    name: '${abbrs.ai.aiFoundry}${resourceToken}'
    location: location
    kind: 'AIServices'
    sku: 'S0'
    customSubDomainName: '${abbrs.ai.aiFoundry}${resourceToken}'
    projectName: '${abbrs.ai.aiFoundryProject}${resourceToken}'
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

// use existing or newly created
var aiServicesEndpoint = useExistingAiProject ? existingAiFoundryEndpoint : aiServices!.outputs.endpoint
var aiServicesName = useExistingAiProject ? existingAiFoundryServiceName : aiServices!.outputs.name

// ========== Content Understanding (separate region) ========== //
var cuResourceName = '${abbrs.ai.aiFoundry}${resourceToken}-cu'
module cuServices 'modules/ai-services.bicep' = {
  name: 'cu-services'
  scope: rg
  params: {
    name: cuResourceName
    location: contentUnderstandingLocation
    kind: 'AIServices'
    sku: 'S0'
    customSubDomainName: cuResourceName
    publicNetworkAccess: 'Enabled'
    deployments: []
  }
}

var cuEndpoint = 'https://${cuResourceName}.services.ai.azure.com/'

// ========== AI Search ========== //
var aiSearchName = '${abbrs.ai.aiSearch}${resourceToken}'
var aiSearchConnectionName = 'search-connection-${resourceToken}'

module search 'modules/search.bicep' = {
  name: 'search'
  scope: rg
  params: {
    name: aiSearchName
    location: location
    tags: tags
  }
}

// ========== AI Search → AI Foundry Connection ========== //
module searchConnection 'modules/deploy_aifp_aisearch_connection.bicep' = if (!useExistingAiProject) {
  name: 'ai-search-connection'
  scope: rg
  params: {
    existingAIProjectName: '${abbrs.ai.aiFoundryProject}${resourceToken}'
    existingAIFoundryName: '${abbrs.ai.aiFoundry}${resourceToken}'
    aiSearchName: aiSearchName
    aiSearchResourceId: search.outputs.id
    aiSearchLocation: location
    aiSearchConnectionName: aiSearchConnectionName
  }
  dependsOn: [
    aiServices
  ]
}

// ========== Storage Account ========== //
module storage 'modules/storage.bicep' = {
  name: 'storage'
  scope: rg
  params: {
    name: '${abbrs.storage.storageAccount}${resourceToken}'
    location: location
    tags: tags
  }
}

// ========== SQL Database ========== //
module sql 'modules/sql.bicep' = {
  name: 'sql'
  scope: rg
  params: {
    serverName: '${abbrs.databases.sqlDatabaseServer}${resourceToken}'
    databaseName: '${abbrs.databases.sqlDatabase}${resourceToken}'
    location: location
    tags: tags
    adminObjectId: deployer().objectId
  }
}

// ========== Cosmos DB (optional) ========== //
module cosmos 'modules/cosmos.bicep' = if (deployCosmos) {
  name: 'cosmos'
  scope: rg
  params: {
    name: '${abbrs.databases.cosmosDBDatabase}${resourceToken}'
    location: location
    tags: tags
    databaseName: 'km-db'
  }
}

// ========== App Service Plan ========== //
var webServerFarmResourceName = '${abbrs.compute.appServicePlan}${resourceToken}'
module webServerFarm 'modules/app-service-plan.bicep' = {
  name: 'deploy_app_service_plan_serverfarm'
  scope: rg
  params: {
    name: webServerFarmResourceName
    location: location
    tags: tags
  }
}

// ========== Backend Web App ========== //
var backendWebSiteResourceName = 'api-${resourceToken}'
module webSiteBackend 'modules/web-sites.bicep' = {
  name: take('module.web-sites.${backendWebSiteResourceName}', 64)
  scope: rg
  params: {
    name: backendWebSiteResourceName
    tags: union(tags, { 'azd-service-name': 'backend' })
    location: location
    kind: 'app,linux'
    serverFarmResourceId: webServerFarm.outputs.id
    managedIdentities: {
      systemAssigned: true
    }
    siteConfig: {
      linuxFxVersion: !empty(backendContainerRegistryHostname) ? 'DOCKER|${backendContainerRegistryHostname}/${backendContainerImageName}:${backendContainerImageTag}' : 'PYTHON|3.13'
      appCommandLine: !empty(backendContainerRegistryHostname) ? '' : 'pip install -r requirements.txt && uvicorn src.api.main:app --host 0.0.0.0 --port 8000'
      acrUseManagedIdentityCreds: !empty(backendContainerRegistryHostname)
      minTlsVersion: '1.2'
    }
    configs: [
      {
        name: 'appsettings'
        properties: {
          DOCKER_REGISTRY_SERVER_URL: !empty(backendContainerRegistryHostname) ? 'https://${backendContainerRegistryHostname}' : ''
          WEBSITES_PORT: '8000'
          AZURE_OPENAI_ENDPOINT: aiServicesEndpoint
          AZURE_OPENAI_CHAT_DEPLOYMENT: chatDeploymentName
          AZURE_OPENAI_EMBEDDING_DEPLOYMENT: embeddingDeploymentName
          AZURE_SEARCH_ENDPOINT: search.outputs.endpoint
          AZURE_SEARCH_INDEX_NAME: 'knowledge-mining-index'
          AZURE_CONTENT_UNDERSTANDING_ENDPOINT: cuEndpoint
          AZURE_STORAGE_ACCOUNT: storage.outputs.accountName
          AZURE_SQL_SERVER: sql.outputs.serverFqdn
          AZURE_SQL_DATABASE: '${abbrs.databases.sqlDatabase}${resourceToken}'
          AZURE_COSMOS_ENDPOINT: deployCosmos ? cosmos!.outputs.endpoint : ''
          AZURE_COSMOS_DATABASE: deployCosmos ? 'km-db' : ''
          AZURE_AD_TENANT_ID: azureAdTenantId
          AZURE_AD_CLIENT_ID: azureAdClientId
          AZURE_AI_AGENT_ENDPOINT: useExistingAiProject ? existingAiFoundryEndpoint : aiServices!.outputs.aiProjectInfo.apiEndpoint
          AZURE_AI_SEARCH_CONNECTION_NAME: useExistingAiProject ? existingAiSearchConnectionName : aiSearchConnectionName
          API_APP_NAME: backendWebSiteResourceName
          APP_FRONTEND_HOSTNAME: '${frontendWebSiteResourceName}.azurewebsites.net'
          APP_ENV: 'Prod'
        }
      }
    ]
  }
}

// ========== Frontend Web App ========== //
var frontendWebSiteResourceName = 'app-${resourceToken}'
module webSiteFrontend 'modules/web-sites.bicep' = {
  name: take('module.web-sites.${frontendWebSiteResourceName}', 64)
  scope: rg
  params: {
    name: frontendWebSiteResourceName
    tags: union(tags, { 'azd-service-name': 'frontend' })
    location: location
    kind: 'app,linux'
    serverFarmResourceId: webServerFarm.outputs.id
    managedIdentities: {
      systemAssigned: true
    }
    siteConfig: {
      linuxFxVersion: !empty(frontendContainerRegistryHostname) ? 'DOCKER|${frontendContainerRegistryHostname}/${frontendContainerImageName}:${frontendContainerImageTag}' : 'NODE|22-lts'
      appCommandLine: !empty(frontendContainerRegistryHostname) ? '' : 'pm2 serve /home/site/wwwroot --no-daemon --spa --port 8080'
      acrUseManagedIdentityCreds: !empty(frontendContainerRegistryHostname)
      minTlsVersion: '1.2'
    }
    configs: [
      {
        name: 'appsettings'
        properties: {
          DOCKER_REGISTRY_SERVER_URL: !empty(frontendContainerRegistryHostname) ? 'https://${frontendContainerRegistryHostname}' : ''
          APP_API_BASE_URL: 'https://${webSiteBackend.outputs.defaultHostname}'
          WEBSITES_PORT: !empty(frontendContainerRegistryHostname) ? '' : '8080'
        }
      }
    ]
  }
}

// ========== Role Assignments ========== //
module roles 'modules/roles.bicep' = {
  name: 'roles'
  scope: rg
  params: {
    openaiName: aiServicesName
    searchName: search.outputs.name
    storageName: storage.outputs.accountName
    cosmosName: deployCosmos ? cosmos!.outputs.name : ''
    cuName: cuResourceName
    backendPrincipalId: webSiteBackend.outputs.systemAssignedMIPrincipalId!
    frontendPrincipalId: webSiteFrontend.outputs.systemAssignedMIPrincipalId!
    acrName: !empty(backendContainerRegistryHostname) ? split(backendContainerRegistryHostname, '.')[0] : ''
    deployerPrincipalId: deployer().objectId
  }
}

// ========== Outputs ========== //
@description('Azure OpenAI endpoint URL.')
output AZURE_OPENAI_ENDPOINT string = aiServicesEndpoint

@description('Azure AI Search endpoint URL.')
output AZURE_SEARCH_ENDPOINT string = search.outputs.endpoint

@description('Azure Content Understanding endpoint URL.')
output AZURE_CONTENT_UNDERSTANDING_ENDPOINT string = cuEndpoint

@description('Azure Storage account name.')
output AZURE_STORAGE_ACCOUNT string = storage.outputs.accountName

@description('Azure SQL Server FQDN.')
output AZURE_SQL_SERVER string = sql.outputs.serverFqdn

@description('Azure SQL Database name.')
output AZURE_SQL_DATABASE string = '${abbrs.databases.sqlDatabase}${resourceToken}'

@description('Azure Cosmos DB endpoint (empty if not deployed).')
output AZURE_COSMOS_ENDPOINT string = deployCosmos ? cosmos!.outputs.endpoint : ''

@description('Azure AI Agent endpoint URL.')
output AZURE_AI_AGENT_ENDPOINT string = useExistingAiProject ? '${existingAiFoundryEndpoint}/projects/${existingAiFoundryProjectName}' : aiServices!.outputs.aiProjectInfo.apiEndpoint

@description('Backend API application URL.')
output API_APP_URL string = 'https://${webSiteBackend.outputs.defaultHostname}'

@description('Frontend web application URL.')
output WEB_APP_URL string = 'https://${webSiteFrontend.outputs.defaultHostname}'

@description('Backend service URI (used by azd).')
output SERVICE_BACKEND_URI string = 'https://${webSiteBackend.outputs.defaultHostname}'

@description('Frontend service URI (used by azd).')
output SERVICE_FRONTEND_URI string = 'https://${webSiteFrontend.outputs.defaultHostname}'

@description('AI Search connection name in AI Foundry.')
output AZURE_AI_SEARCH_CONNECTION_NAME string = useExistingAiProject ? existingAiSearchConnectionName : aiSearchConnectionName
