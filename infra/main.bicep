// ========== main.bicep ========== //
targetScope = 'resourceGroup'
var abbrs = loadJsonContent('./abbreviations.json')
@minLength(3)
@maxLength(20)
@description('A unique prefix for all resources in this deployment. This should be 3-20 characters long:')
param environmentName string

@minLength(1)
@description('Location for the Content Understanding service deployment:')
@allowed(['swedencentral', 'australiaeast'])
@metadata({
  azd: {
    type: 'location'
  }
})
param contentUnderstandingLocation string

@minLength(1)
@description('Secondary location for databases creation(example:eastus2):')
param secondaryLocation string

@minLength(1)
@description('GPT model deployment type:')
@allowed([
  'Standard'
  'GlobalStandard'
])
param deploymentType string = 'GlobalStandard'

@minLength(1)
@description('Name of the GPT model to deploy:')
@allowed([
  'gpt-4o-mini'
  'gpt-4o'
  'gpt-4'
])
param gptModelName string = 'gpt-4o-mini'

// @minLength(1)
// @description('Version of the GPT model to deploy:')
// param gptModelVersion string = '2024-02-15-preview' //'2024-08-06'
var azureOpenAIApiVersion = '2024-02-15-preview'

@minValue(10)
@description('Capacity of the GPT deployment:')
// You can increase this, but capacity is limited per model/region, so you will get errors if you go over
// https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits
param gptDeploymentCapacity int = 30

@minLength(1)
@description('Name of the Text Embedding model to deploy:')
@allowed([
  'text-embedding-ada-002'
])
param embeddingModel string = 'text-embedding-ada-002'

@minValue(10)
@description('Capacity of the Embedding Model deployment')
param embeddingDeploymentCapacity int = 80

param imageTag string = 'latest_migrated'

param AZURE_LOCATION string=''
var solutionLocation = empty(AZURE_LOCATION) ? resourceGroup().location : AZURE_LOCATION

var uniqueId = toLower(uniqueString(subscription().id, environmentName, solutionLocation))
var solutionPrefix = 'km${padLeft(take(uniqueId, 12), 12, '0')}'
// var resourceGroupName = resourceGroup().name

var baseUrl = 'https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/'

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
    solutionLocation: solutionLocation
    keyVaultName: kvault.outputs.keyvaultName
    cuLocation: contentUnderstandingLocation
    deploymentType: gptModelName == 'gpt-4' ? 'Standard' : deploymentType
    gptModelName: gptModelName
    azureOpenAIApiVersion: azureOpenAIApiVersion
    gptDeploymentCapacity: gptDeploymentCapacity
    embeddingModel: embeddingModel
    embeddingDeploymentCapacity: embeddingDeploymentCapacity
    managedIdentityObjectId: managedIdentityModule.outputs.managedIdentityOutput.objectId
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
    managedIdentityObjectId: managedIdentityModule.outputs.managedIdentityOutput.objectId
  }
  scope: resourceGroup(resourceGroup().name)
}

//========== Updates to Key Vault ========== //
resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: aifoundry.outputs.keyvaultName
  scope: resourceGroup(resourceGroup().name)
}

//========== Deployment script to upload sample data ========== //
module uploadFiles 'deploy_post_deployment_scripts.bicep' = {
  name : 'deploy_post_deployment_scripts'
  params:{
    solutionLocation: secondaryLocation
    baseUrl: baseUrl
    storageAccountName: storageAccount.outputs.storageName
    containerName: storageAccount.outputs.storageContainer
    containerAppName: '${abbrs.containers.containerApp}${solutionPrefix}'
    environmentName: '${abbrs.containers.containerAppsEnvironment}${solutionPrefix}'
    managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.id
    managedIdentityClientId:managedIdentityModule.outputs.managedIdentityOutput.clientId
    keyVaultName:aifoundry.outputs.keyvaultName
    logAnalyticsWorkspaceResourceName: aifoundry.outputs.logAnalyticsWorkspaceResourceName
    sqlServerName: sqlDBModule.outputs.sqlServerName
    sqlDbName: sqlDBModule.outputs.sqlDbName
    sqlUsers: [
      {
        principalId: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
        principalName: managedIdentityModule.outputs.managedIdentityBackendAppOutput.name
        databaseRoles: ['db_datareader', 'db_datawriter']
      }
    ]
  }
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
    imageTag: imageTag
    appServicePlanId: hostingplan.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    azureAiProjectConnString: keyVault.getSecret('AZURE-AI-PROJECT-CONN-STRING')
    userassignedIdentityId: managedIdentityModule.outputs.managedIdentityBackendAppOutput.id
    aiProjectName: aifoundry.outputs.aiProjectName
    keyVaultName: kvault.outputs.keyvaultName
    appSettings: {
      AZURE_OPEN_AI_DEPLOYMENT_MODEL: gptModelName
      AZURE_OPEN_AI_ENDPOINT: aifoundry.outputs.aiServicesTarget
      AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
      AZURE_OPENAI_RESOURCE: aifoundry.outputs.aiServicesName
      AZURE_OPENAI_API_KEY: '@Microsoft.KeyVault(SecretUri=${kvault.outputs.keyvaultUri}secrets/AZURE-OPENAI-KEY/)'
      USE_CHAT_HISTORY_ENABLED: 'True'
      AZURE_COSMOSDB_ACCOUNT: cosmosDBModule.outputs.cosmosAccountName
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: cosmosDBModule.outputs.cosmosContainerName
      AZURE_COSMOSDB_DATABASE: cosmosDBModule.outputs.cosmosDatabaseName
      AZURE_COSMOSDB_ENABLE_FEEDBACK: 'True'
      SQLDB_DATABASE: sqlDBModule.outputs.sqlDbName
      SQLDB_SERVER: sqlDBModule.outputs.sqlServerName
      SQLDB_USERNAME: sqlDBModule.outputs.sqlDbUser
      SQLDB_USER_MID: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId

      OPENAI_API_VERSION: azureOpenAIApiVersion
      AZURE_AI_SEARCH_ENDPOINT: aifoundry.outputs.aiSearchTarget
      AZURE_AI_SEARCH_API_KEY: '@Microsoft.KeyVault(SecretUri=${kvault.outputs.keyvaultUri}secrets/AZURE-SEARCH-KEY/)'
      AZURE_AI_SEARCH_INDEX: 'call_transcripts_index'
      USE_AI_PROJECT_CLIENT: 'False'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: aifoundry.outputs.applicationInsightsConnectionString
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
output AZURE_AI_PROJECT_CONN_STRING string = aifoundry.outputs.azureProjectConnString
output AZURE_AI_PROJECT_NAME string = aifoundry.outputs.azureProjectName
output AZURE_AI_SEARCH_API_KEY string = ''
output AZURE_AI_SEARCH_ENDPOINT string = aifoundry.outputs.aiSearchTarget
output AZURE_AI_SEARCH_INDEX string = 'call_transcripts_index'
output AZURE_COSMOSDB_ACCOUNT string = cosmosDBModule.outputs.cosmosAccountName
output AZURE_COSMOSDB_CONVERSATIONS_CONTAINER string = 'conversations'
output AZURE_COSMOSDB_DATABASE string = 'db_conversation_history'
output AZURE_COSMOSDB_ENABLE_FEEDBACK string = 'True'
output AZURE_OPEN_AI_DEPLOYMENT_MODEL string = gptModelName
output AZURE_OPEN_AI_DEPLOYMENT_MODEL_CAPACITY int = gptDeploymentCapacity
output AZURE_OPEN_AI_ENDPOINT string = aifoundry.outputs.aiServicesTarget
output AZURE_OPENAI_API_KEY string = ''
output AZURE_OPEN_AI_MODEL_DEPLOYMENT_TYPE string = gptModelName == 'gpt-4' ? 'Standard' : deploymentType
output AZURE_OPENAI_EMBEDDING_MODEL string = embeddingModel
output AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY int = embeddingDeploymentCapacity
output AZURE_OPENAI_API_VERSION string = azureOpenAIApiVersion
output AZURE_OPENAI_RESOURCE string = aifoundry.outputs.aiServicesName
output OPENAI_API_VERSION string = azureOpenAIApiVersion
output REACT_APP_LAYOUT_CONFIG string = backend_docker.outputs.reactAppLayoutConfig
output SQLDB_DATABASE string = sqlDBModule.outputs.sqlDbName
output SQLDB_SERVER string = sqlDBModule.outputs.sqlServerName
output SQLDB_USER_MID string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
output SQLDB_USERNAME string = sqlDBModule.outputs.sqlDbUser
output USE_AI_PROJECT_CLIENT string = 'False'
output USE_CHAT_HISTORY_ENABLED string = 'True'
output DISPLAY_CHART_DEFAULT string = 'False'

output API_APP_URL string = backend_docker.outputs.appUrl
output WEB_APP_URL string = frontend_docker.outputs.appUrl
output APPLICATIONINSIGHTS_CONNECTION_STRING string = aifoundry.outputs.applicationInsightsConnectionString
