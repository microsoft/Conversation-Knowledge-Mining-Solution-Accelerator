// ========== main.bicep ========== //
targetScope = 'resourceGroup'
var abbrs = loadJsonContent('./abbreviations.json')
@minLength(3)
@maxLength(20)
@description('A unique prefix for all resources in this deployment. This should be 3-20 characters long:')
param environmentName string

@description('Optional: Existing Log Analytics Workspace Resource ID')
param existingLogAnalyticsWorkspaceId string = ''

@description('Use this parameter to use an existing AI project resource ID')
param azureExistingAIProjectResourceId string = ''

@minLength(1)
@description('Location for the Content Understanding service deployment:')
@allowed(['swedencentral', 'australiaeast'])
@metadata({
  azd: {
    type: 'location'
  }
})
param contentUnderstandingLocation string = 'swedencentral'

@minLength(1)
@description('Secondary location for databases creation(example:eastus2):')
param secondaryLocation string = 'eastus2'

@minLength(1)
@description('GPT model deployment type:')
@allowed([
  'Standard'
  'GlobalStandard'
])
param deploymentType string = 'GlobalStandard'

@description('Name of the GPT model to deploy:')
param gptModelName string = 'gpt-4o-mini'

@description('Version of the GPT model to deploy:')
param gptModelVersion string = '2024-07-18'

param azureOpenAIApiVersion string = '2025-01-01-preview'

param azureAiAgentApiVersion string = '2025-05-01'

@minValue(10)
@description('Capacity of the GPT deployment:')
// You can increase this, but capacity is limited per model/region, so you will get errors if you go over
// https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits
param gptDeploymentCapacity int = 150

@minLength(1)
@description('Name of the Text Embedding model to deploy:')
@allowed([
  'text-embedding-ada-002'
])
param embeddingModel string = 'text-embedding-ada-002'

@minValue(10)
@description('Capacity of the Embedding Model deployment')
param embeddingDeploymentCapacity int = 80

param imageTag string = 'latest_fdp'

param AZURE_LOCATION string=''
var solutionLocation = empty(AZURE_LOCATION) ? resourceGroup().location : AZURE_LOCATION

var uniqueId = toLower(uniqueString(subscription().id, environmentName, solutionLocation, resourceGroup().name))


@metadata({
  azd:{
    type: 'location'
    usageName: [
      'OpenAI.GlobalStandard.gpt-4o-mini,150'
      'OpenAI.GlobalStandard.text-embedding-ada-002,80'
    ]
  }
})
@description('Location for AI Foundry deployment. This is the location where the AI Foundry resources will be deployed.')
param aiDeploymentsLocation string

var solutionPrefix = 'km${padLeft(take(uniqueId, 12), 12, '0')}'

var acrName = 'kmcontainerreg'

var baseUrl = 'https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/'

// ========== Resource Group Tag ========== //
resource resourceGroupTags 'Microsoft.Resources/tags@2021-04-01' = {
  name: 'default'
  properties: {
    tags: {
      TemplateName: 'KM Generic'
    }
  }
}

// ========== Managed Identity ========== //
module managedIdentityModule 'deploy_managed_identity.bicep' = {
  name: 'deploy_managed_identity'
  params: {
    miName:'${abbrs.security.managedIdentity}${solutionPrefix}'
    solutionName: solutionPrefix
    solutionLocation: solutionLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

// ==========Key Vault Module ========== //
module kvault 'deploy_keyvault.bicep' = {
  name: 'deploy_keyvault'
  params: {
    keyvaultName: '${abbrs.security.keyVault}${solutionPrefix}'
    solutionLocation: solutionLocation
    managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.objectId
  }
  scope: resourceGroup(resourceGroup().name)
}

// ==========AI Foundry and related resources ========== //
module aifoundry 'deploy_ai_foundry.bicep' = {
  name: 'deploy_ai_foundry'
  params: {
    solutionName: solutionPrefix
    solutionLocation: aiDeploymentsLocation
    keyVaultName: kvault.outputs.keyvaultName
    cuLocation: contentUnderstandingLocation
    deploymentType: deploymentType
    gptModelName: gptModelName
    gptModelVersion: gptModelVersion
    azureOpenAIApiVersion: azureOpenAIApiVersion
    gptDeploymentCapacity: gptDeploymentCapacity
    embeddingModel: embeddingModel
    embeddingDeploymentCapacity: embeddingDeploymentCapacity
    managedIdentityObjectId: managedIdentityModule.outputs.managedIdentityOutput.objectId
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
    azureExistingAIProjectResourceId: azureExistingAIProjectResourceId

  }
  scope: resourceGroup(resourceGroup().name)
}


// ========== Storage account module ========== //
module storageAccount 'deploy_storage_account.bicep' = {
  name: 'deploy_storage_account'
  params: {
    saName: '${abbrs.storage.storageAccount}${solutionPrefix}'
    solutionLocation: solutionLocation
    keyVaultName: kvault.outputs.keyvaultName
    managedIdentityObjectId: managedIdentityModule.outputs.managedIdentityOutput.objectId
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Cosmos DB module ========== //
module cosmosDBModule 'deploy_cosmos_db.bicep' = {
  name: 'deploy_cosmos_db'
  params: {
    accountName: '${abbrs.databases.cosmosDBDatabase}${solutionPrefix}'
    solutionLocation: secondaryLocation
    keyVaultName: kvault.outputs.keyvaultName
  }
  scope: resourceGroup(resourceGroup().name)
}

//========== SQL DB module ========== //
module sqlDBModule 'deploy_sql_db.bicep' = {
  name: 'deploy_sql_db'
  params: {
    serverName: '${abbrs.databases.sqlDatabaseServer}${solutionPrefix}'
    sqlDBName: '${abbrs.databases.sqlDatabase}${solutionPrefix}'
    solutionLocation: secondaryLocation
    keyVaultName: kvault.outputs.keyvaultName
    managedIdentityName: managedIdentityModule.outputs.managedIdentityOutput.name
    sqlUsers: [
      {
        principalId: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
        principalName: managedIdentityModule.outputs.managedIdentityBackendAppOutput.name
        databaseRoles: ['db_datareader', 'db_datawriter']
      }
    ]
  }
  scope: resourceGroup(resourceGroup().name)
}

//========== Deployment script to upload sample data ========== //
module uploadFiles 'deploy_upload_files_script.bicep' = {
  name : 'deploy_upload_files_script'
  params:{
    solutionLocation: secondaryLocation
    baseUrl: baseUrl
    storageAccountName: storageAccount.outputs.storageName
    containerName: storageAccount.outputs.storageContainer
    managedIdentityResourceId:managedIdentityModule.outputs.managedIdentityOutput.id
    managedIdentityClientId:managedIdentityModule.outputs.managedIdentityOutput.clientId
  }
}

//========== Deployment script to process and index data ========== //
module createIndex 'deploy_index_scripts.bicep' = {
  name : 'deploy_index_scripts'
  params:{
    solutionLocation: secondaryLocation
    managedIdentityResourceId:managedIdentityModule.outputs.managedIdentityOutput.id
    managedIdentityClientId:managedIdentityModule.outputs.managedIdentityOutput.clientId
    baseUrl:baseUrl
    keyVaultName:aifoundry.outputs.keyvaultName
  }
  dependsOn:[sqlDBModule,uploadFiles]
}

module hostingplan 'deploy_app_service_plan.bicep' = {
  name: 'deploy_app_service_plan'
  params: {
    solutionLocation: solutionLocation
    HostingPlanName: '${abbrs.compute.appServicePlan}${solutionPrefix}'
  }
}

module backend_docker 'deploy_backend_docker.bicep' = {
  name: 'deploy_backend_docker'
  params: {
    name: 'api-${solutionPrefix}'
    solutionLocation: solutionLocation
    aideploymentsLocation: aiDeploymentsLocation
    imageTag: imageTag
    acrName: acrName
    appServicePlanId: hostingplan.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    userassignedIdentityId: managedIdentityModule.outputs.managedIdentityBackendAppOutput.id
    keyVaultName: kvault.outputs.keyvaultName
    aiServicesName: aifoundry.outputs.aiServicesName
    azureExistingAIProjectResourceId: azureExistingAIProjectResourceId
    aiSearchName: aifoundry.outputs.aiSearchName 
    appSettings: {
      AZURE_OPENAI_DEPLOYMENT_MODEL: gptModelName
      AZURE_OPENAI_ENDPOINT: aifoundry.outputs.aiServicesTarget
      AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
      AZURE_OPENAI_RESOURCE: aifoundry.outputs.aiServicesName
      AZURE_AI_AGENT_ENDPOINT: aifoundry.outputs.projectEndpoint
      AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
      AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
      USE_CHAT_HISTORY_ENABLED: 'True'
      AZURE_COSMOSDB_ACCOUNT: cosmosDBModule.outputs.cosmosAccountName
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: cosmosDBModule.outputs.cosmosContainerName
      AZURE_COSMOSDB_DATABASE: cosmosDBModule.outputs.cosmosDatabaseName
      AZURE_COSMOSDB_ENABLE_FEEDBACK: 'True'
      SQLDB_DATABASE: sqlDBModule.outputs.sqlDbName
      SQLDB_SERVER: sqlDBModule.outputs.sqlServerName
      SQLDB_USER_MID: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId

      AZURE_AI_SEARCH_ENDPOINT: aifoundry.outputs.aiSearchTarget
      AZURE_AI_SEARCH_INDEX: 'call_transcripts_index'
      AZURE_AI_SEARCH_CONNECTION_NAME: aifoundry.outputs.aiSearchConnectionName
      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: aifoundry.outputs.applicationInsightsConnectionString
      DUMMY_TEST: 'True'
      SOLUTION_NAME: solutionPrefix
      APP_ENV: 'Prod'
    }
  }
  scope: resourceGroup(resourceGroup().name)
}

module frontend_docker 'deploy_frontend_docker.bicep' = {
  name: 'deploy_frontend_docker'
  params: {
    name: '${abbrs.compute.webApp}${solutionPrefix}'
    solutionLocation:solutionLocation
    imageTag: imageTag
    acrName: acrName
    appServicePlanId: hostingplan.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    appSettings:{
      APP_API_BASE_URL:backend_docker.outputs.appUrl
    }
  }
  scope: resourceGroup(resourceGroup().name)
}

output SOLUTION_NAME string = solutionPrefix
output RESOURCE_GROUP_NAME string = resourceGroup().name
output RESOURCE_GROUP_LOCATION string = solutionLocation
output ENVIRONMENT_NAME string = environmentName
output AZURE_CONTENT_UNDERSTANDING_LOCATION string = contentUnderstandingLocation
output AZURE_SECONDARY_LOCATION string = secondaryLocation
output APPINSIGHTS_INSTRUMENTATIONKEY string = backend_docker.outputs.appInsightInstrumentationKey
output AZURE_AI_PROJECT_CONN_STRING string = aifoundry.outputs.projectEndpoint
output AZURE_AI_AGENT_API_VERSION string = azureAiAgentApiVersion
output AZURE_AI_FOUNDRY_NAME string = aifoundry.outputs.aiServicesName
output AZURE_AI_PROJECT_NAME string = aifoundry.outputs.aiProjectName
output AZURE_AI_SEARCH_NAME string = aifoundry.outputs.aiSearchName
output AZURE_AI_SEARCH_ENDPOINT string = aifoundry.outputs.aiSearchTarget
output AZURE_AI_SEARCH_INDEX string = 'call_transcripts_index'
output AZURE_AI_SEARCH_CONNECTION_NAME string = aifoundry.outputs.aiSearchConnectionName
output AZURE_COSMOSDB_ACCOUNT string = cosmosDBModule.outputs.cosmosAccountName
output AZURE_COSMOSDB_CONVERSATIONS_CONTAINER string = 'conversations'
output AZURE_COSMOSDB_DATABASE string = 'db_conversation_history'
output AZURE_COSMOSDB_ENABLE_FEEDBACK string = 'True'
output AZURE_OPENAI_DEPLOYMENT_MODEL string = gptModelName
output AZURE_OPENAI_DEPLOYMENT_MODEL_CAPACITY int = gptDeploymentCapacity
output AZURE_OPENAI_ENDPOINT string = aifoundry.outputs.aiServicesTarget
output AZURE_OPENAI_MODEL_DEPLOYMENT_TYPE string = deploymentType
output AZURE_OPENAI_EMBEDDING_MODEL string = embeddingModel
output AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY int = embeddingDeploymentCapacity
output AZURE_OPENAI_API_VERSION string = azureOpenAIApiVersion
output AZURE_OPENAI_RESOURCE string = aifoundry.outputs.aiServicesName
output REACT_APP_LAYOUT_CONFIG string = backend_docker.outputs.reactAppLayoutConfig
output SQLDB_DATABASE string = sqlDBModule.outputs.sqlDbName
output SQLDB_SERVER string = sqlDBModule.outputs.sqlServerName
output SQLDB_USER_MID string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
output USE_AI_PROJECT_CLIENT string = 'False'
output USE_CHAT_HISTORY_ENABLED string = 'True'
output DISPLAY_CHART_DEFAULT string = 'False'
output AZURE_AI_AGENT_ENDPOINT string = aifoundry.outputs.projectEndpoint
output AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME string = gptModelName
output ACR_NAME string = acrName
output AZURE_ENV_IMAGETAG string = imageTag
output AZURE_EXISTING_AI_PROJECT_RESOURCE_ID string = azureExistingAIProjectResourceId
output APPLICATIONINSIGHTS_CONNECTION_STRING string = aifoundry.outputs.applicationInsightsConnectionString

output API_APP_URL string = backend_docker.outputs.appUrl
output WEB_APP_URL string = frontend_docker.outputs.appUrl

output BACKEND_APP_NAME string = backend_docker.outputs.backendAppName
output FRONTEND_APP_NAME string = frontend_docker.outputs.frontendAppName
output BACKEND_MANAGED_IDENTITY_PRINCIPAL_ID string = backend_docker.outputs.backendManagedIdentityPrincipalId
output FRONTEND_MANAGED_IDENTITY_PRINCIPAL_ID string = frontend_docker.outputs.frontendManagedIdentityPrincipalId
