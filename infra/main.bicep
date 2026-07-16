targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the environment (e.g., dev, prod)')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Name of the Azure OpenAI chat deployment')
param chatDeploymentName string = 'gpt-5.2'

@description('Name of the Azure OpenAI embedding deployment')
param embeddingDeploymentName string = 'text-embedding-3-small'

@description('GPT model version')
param gptModelVersion string = '2025-12-11'

@description('Azure AD tenant ID for authentication')
param azureAdTenantId string = ''

@description('Azure AD client ID for authentication')
param azureAdClientId string = ''

@description('Optional. The tags to apply to all deployed Azure resources.')
param tags resourceInput<'Microsoft.Resources/resourceGroups@2025-04-01'>.tags = {}

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

@description('Admin API key for script-based authentication (setup-data, post-deploy scripts). Leave empty to disable.')
@secure()
param adminApiKey string = ''

// ── Container Image Configuration ──
// Images are built and pushed to the dedicated ACR provisioned below by the
// post-deployment script (infra/scripts/build-images.ps1). App Services boot on
// a public hello-world image and are switched to these images by that script.
@description('Backend container image name (repository) to build and push to the provisioned ACR')
param backendContainerImageName string = 'km-api'

@description('Backend container image tag')
param backendContainerImageTag string = 'latest'

@description('Frontend container image name (repository) to build and push to the provisioned ACR')
param frontendContainerImageName string = 'km-app'

@description('Frontend container image tag')
param frontendContainerImageTag string = 'latest'

var abbrs = loadJsonContent('abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

var existingTags = resourceGroup().tags ?? {}

// ========== Resource Group Tag ========== //
resource resourceGroupTags 'Microsoft.Resources/tags@2025-04-01' = {
  name: 'default'
  properties: {
    tags: union(
      existingTags,
      tags,
      {
        TemplateName: 'KM-Generic'
        DeploymentName: deployment().name
        SecurityControl:'Ignore'
        CostControl:'Ignore'
        Purpose:'Knowledge Mining Modularity'
      }
    )
  }
}

// ========== AI Foundry: AI Services ========== //
module aiServices 'modules/ai-services.bicep' = if (!useExistingAiProject) {
  name: 'ai-services'
  params: {
    name: '${abbrs.ai.aiFoundry}${resourceToken}'
    location: location
    kind: 'AIServices'
    sku: 'S0'
    customSubDomainName: '${abbrs.ai.aiFoundry}${resourceToken}'
    projectName: '${abbrs.ai.aiFoundryProject}${resourceToken}'
    projectDescription: 'Knowledge Mining AI Foundry Project'
    publicNetworkAccess: 'Enabled'
    restrictOutboundNetworkAccess: false
    disableLocalAuth: false
    restore: false
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
          capacity: 150
        }
      }
      {
        name: embeddingDeploymentName
        model: {
          format: 'OpenAI'
          name: embeddingDeploymentName
          version: '1'
        }
        sku: {
          name: 'GlobalStandard'
          capacity: 80
        }
      }
    ]
  }
}

// use existing or newly created
var aiServicesEndpoint = useExistingAiProject ? existingAiFoundryEndpoint : aiServices!.outputs.endpoint
var aiServicesName = useExistingAiProject ? existingAiFoundryServiceName : aiServices!.outputs.name

// ========== AI Search ========== //
var aiSearchName = '${abbrs.ai.aiSearch}${resourceToken}'
var aiSearchConnectionName = 'search-connection-${resourceToken}'

module search 'modules/search.bicep' = {
  name: 'search'
  params: {
    name: aiSearchName
    location: location
    tags: tags
  }
}

// ========== AI Search → AI Foundry Connection ========== //
module searchConnection 'modules/deploy_aifp_aisearch_connection.bicep' = if (!useExistingAiProject) {
  name: 'ai-search-connection'
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
  params: {
    name: '${abbrs.storage.storageAccount}${resourceToken}'
    location: location
    tags: tags
  }
}

// ========== SQL Database ========== //
module sql 'modules/sql.bicep' = {
  name: 'sql'
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
  params: {
    name: '${abbrs.databases.cosmosDBDatabase}${resourceToken}'
    location: location
    tags: tags
    databaseName: 'km-db'
  }
}

// ========== Azure Container Registry ========== //
var acrName = 'cr${resourceToken}'
module containerRegistry 'modules/container-registry.bicep' = {
  name: 'container-registry'
  params: {
    name: acrName
    location: location
    tags: tags
  }
}
var acrLoginServer = containerRegistry.outputs.loginServer

// ========== App Service Plan ========== //
var webServerFarmResourceName = '${abbrs.compute.appServicePlan}${resourceToken}'
module webServerFarm 'modules/app-service-plan.bicep' = {
  name: 'deploy_app_service_plan_serverfarm'
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
      linuxFxVersion: 'DOCKER|mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
      acrUseManagedIdentityCreds: true
      appCommandLine: ''
      minTlsVersion: '1.2'
    }
    configs: [
      {
        name: 'appsettings'
        properties: {
          DOCKER_REGISTRY_SERVER_URL: 'https://${acrLoginServer}'
          WEBSITES_PORT: '8000'
          AZURE_OPENAI_ENDPOINT: aiServicesEndpoint
          AZURE_OPENAI_CHAT_DEPLOYMENT: chatDeploymentName
          AZURE_OPENAI_EMBEDDING_DEPLOYMENT: embeddingDeploymentName
          AZURE_SEARCH_ENDPOINT: search.outputs.endpoint
          AZURE_SEARCH_INDEX_NAME: 'knowledge-mining-index'
          AZURE_CONTENT_UNDERSTANDING_ENDPOINT: aiServices!.outputs.endpoints['Content Understanding']
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
          APP_FRONTEND_HOSTNAME: 'https://${frontendWebSiteResourceName}.azurewebsites.net'
          APP_ENV: 'Prod'
          ADMIN_API_KEY: adminApiKey
          SOLUTION_SUFFIX: resourceToken
        }
      }
    ]
  }
}

// ========== Frontend Web App ========== //
var frontendWebSiteResourceName = 'app-${resourceToken}'
module webSiteFrontend 'modules/web-sites.bicep' = {
  name: take('module.web-sites.${frontendWebSiteResourceName}', 64)
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
      linuxFxVersion: 'DOCKER|mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
      acrUseManagedIdentityCreds: true
      appCommandLine: ''
      minTlsVersion: '1.2'
    }
    configs: [
      {
        name: 'appsettings'
        properties: {
          DOCKER_REGISTRY_SERVER_URL: 'https://${acrLoginServer}'
          APP_API_BASE_URL: 'https://${webSiteBackend.outputs.defaultHostname}'
          WEBSITES_PORT: '80'
        }
      }
    ]
  }
}

// ========== Role Assignments ========== //
module roles 'modules/roles.bicep' = {
  name: 'roles'
  params: {
    openaiName: aiServicesName
    searchName: search.outputs.name
    storageName: storage.outputs.accountName
    cosmosName: deployCosmos ? cosmos!.outputs.name : ''
    backendPrincipalId: webSiteBackend.outputs.systemAssignedMIPrincipalId!
    frontendPrincipalId: webSiteFrontend.outputs.systemAssignedMIPrincipalId!
    acrName: containerRegistry.outputs.name
    deployerPrincipalId: deployer().objectId
    aiProjectPrincipalId: useExistingAiProject ? '' : aiServices!.outputs.aiProjectInfo.aiprojectSystemAssignedMIPrincipalId
  }
}

// ========== Outputs ========== //
@description('Azure OpenAI endpoint URL.')
output AZURE_OPENAI_ENDPOINT string = aiServicesEndpoint

@description('Azure AI Search endpoint URL.')
output AZURE_SEARCH_ENDPOINT string = search.outputs.endpoint

@description('Azure Content Understanding endpoint URL.')
output AZURE_CONTENT_UNDERSTANDING_ENDPOINT string = aiServices!.outputs.endpoints['Content Understanding']

@description('Azure Storage account name.')
output AZURE_STORAGE_ACCOUNT string = storage.outputs.accountName

@description('Azure SQL Server FQDN.')
output AZURE_SQL_SERVER string = sql.outputs.serverFqdn

@description('Azure SQL Database name.')
output AZURE_SQL_DATABASE string = '${abbrs.databases.sqlDatabase}${resourceToken}'

@description('Backend API application (and SQL contained user) name.')
output API_APP_NAME string = backendWebSiteResourceName

@description('Backend API system-assigned managed identity principal ID.')
output AZURE_API_PRINCIPAL_ID string = webSiteBackend.outputs.systemAssignedMIPrincipalId!

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

@description('Azure Container Registry name.')
output ACR_NAME string = containerRegistry.outputs.name

@description('Azure Container Registry login server URL.')
output ACR_LOGIN_SERVER string = containerRegistry.outputs.loginServer

@description('Backend container image repository name to build and push to ACR.')
output BACKEND_CONTAINER_IMAGE_NAME string = backendContainerImageName

@description('Backend container image tag to build and push to ACR.')
output BACKEND_CONTAINER_IMAGE_TAG string = backendContainerImageTag

@description('Frontend container image repository name to build and push to ACR.')
output FRONTEND_CONTAINER_IMAGE_NAME string = frontendContainerImageName

@description('Frontend container image tag to build and push to ACR.')
output FRONTEND_CONTAINER_IMAGE_TAG string = frontendContainerImageTag

@description('Frontend web application (App Service) name.')
output FRONTEND_APP_NAME string = frontendWebSiteResourceName

@description('Resource group name.')
output RESOURCE_GROUP_NAME string = resourceGroup().name

@description('Solution resource token suffix used in resource names.')
output SOLUTION_SUFFIX string = resourceToken
