// ========== main.bicep ========== //
targetScope = 'resourceGroup'
//var abbrs = loadJsonContent('./abbreviations.json')
@minLength(3)
@maxLength(15)
@description('Required. A unique prefix for all resources in this deployment. This should be 3-20 characters long:')
param solutionName string = 'kmgen'

@description('Optional: Existing Log Analytics Workspace Resource ID')
param existingLogAnalyticsWorkspaceId string = ''

@description('Optional. Use this parameter to use an existing AI project resource ID')
param azureExistingAIProjectResourceId string = ''

@minLength(1)
@description('Optional. Location for the Content Understanding service deployment:')
@allowed(['swedencentral', 'australiaeast'])
@metadata({
  azd: {
    type: 'location'
  }
})
param contentUnderstandingLocation string = 'swedencentral'

@minLength(1)
@description('Optional. Secondary location for databases creation(example:eastus2):')
param secondaryLocation string = 'eastus2'

@minLength(1)
@description('Optional. GPT model deployment type:')
@allowed([
  'Standard'
  'GlobalStandard'
])
param deploymentType string = 'GlobalStandard'

@description('Optional. Name of the GPT model to deploy:')
param gptModelName string = 'gpt-4o-mini'

@description('Optional. Version of the GPT model to deploy:')
param gptModelVersion string = '2024-07-18'

@description('Optional. Version of the OpenAI.')
param azureOpenAIApiVersion string = '2025-01-01-preview'

@description('Optional. Version of AI Agent API.')
param azureAiAgentApiVersion string = '2025-05-01'

@minValue(10)
@description('Optional. Capacity of the GPT deployment:')
// You can increase this, but capacity is limited per model/region, so you will get errors if you go over
// https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits
param gptDeploymentCapacity int = 150

@minLength(1)
@description('Optional. Name of the Text Embedding model to deploy:')
@allowed([
  'text-embedding-ada-002'
])
param embeddingModel string = 'text-embedding-ada-002'

@minValue(10)
@description('Optional. Capacity of the Embedding Model deployment.')
param embeddingDeploymentCapacity int = 80

@description('Optional. Image Tag.')
param imageTag string = 'latest_fdp'

@description('Optional. Azure Location.')
param AZURE_LOCATION string=''
var solutionLocation = empty(AZURE_LOCATION) ? resourceGroup().location : AZURE_LOCATION

//var uniqueId = toLower(uniqueString(subscription().id, solutionName, solutionLocation, resourceGroup().name))

@metadata({
  azd:{
    type: 'location'
    usageName: [
      'OpenAI.GlobalStandard.gpt-4o-mini,150'
      'OpenAI.GlobalStandard.text-embedding-ada-002,80'
    ]
  }
})
@description('Required. Location for AI Foundry deployment. This is the location where the AI Foundry resources will be deployed.')
param aiDeploymentsLocation string

//var solutionSuffix = 'km${padLeft(take(uniqueId, 12), 12, '0')}'

var acrName = 'kmcontainerreg'

var baseUrl = 'https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/'

@description('Optional. The tags to apply to all deployed Azure resources.')
param tags resourceInput<'Microsoft.Resources/resourceGroups@2025-04-01'>.tags = {}

@maxLength(5)
@description('Optional. A unique text value for the solution. This is used to ensure resource names are unique for global resources. Defaults to a 5-character substring of the unique string generated from the subscription ID, resource group name, and solution name.')
param solutionUniqueText string = substring(uniqueString(subscription().id, resourceGroup().name, solutionName), 0, 5)

var solutionSuffix = toLower(trim(replace(
  replace(
    replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''),
    ' ',
    ''
  ),
  '*',
  ''
)))

// ========== Resource Group Tag ========== //
resource resourceGroupTags 'Microsoft.Resources/tags@2021-04-01' = {
  name: 'default'
  properties: {
    tags: {
      ... tags
      TemplateName: 'KM Generic'
    }
  }
}

// ========== Managed Identity ========== //
module managedIdentityModule 'deploy_managed_identity.bicep' = {
  name: 'deploy_managed_identity'
  params: {
    miName:'id-${solutionSuffix}'
    solutionName: solutionSuffix
    solutionLocation: solutionLocation
    tags : tags
  }
  scope: resourceGroup(resourceGroup().name)
}

// ==========Key Vault Module ========== //
module kvault 'deploy_keyvault.bicep' = {
  name: 'deploy_keyvault'
  params: {
    keyvaultName: 'kv-${solutionSuffix}'
    solutionLocation: solutionLocation
    managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.objectId
    tags : tags
  }
  scope: resourceGroup(resourceGroup().name)
}

// ==========AI Foundry and related resources ========== //
module aifoundry 'deploy_ai_foundry.bicep' = {
  name: 'deploy_ai_foundry'
  params: {
    solutionName: solutionSuffix
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
    tags : tags

  }
  scope: resourceGroup(resourceGroup().name)
}


// ========== Storage account module ========== //
module storageAccount 'deploy_storage_account.bicep' = {
  name: 'deploy_storage_account'
  params: {
    saName: 'st${solutionSuffix}'
    solutionLocation: solutionLocation
    keyVaultName: kvault.outputs.keyvaultName
    managedIdentityObjectId: managedIdentityModule.outputs.managedIdentityOutput.objectId
    tags : tags
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Cosmos DB module ========== //
module cosmosDBModule 'deploy_cosmos_db.bicep' = {
  name: 'deploy_cosmos_db'
  params: {
    accountName: 'cosmos-${solutionSuffix}'
    solutionLocation: secondaryLocation
    keyVaultName: kvault.outputs.keyvaultName
    tags : tags
  }
  scope: resourceGroup(resourceGroup().name)
}

//========== SQL DB module ========== //
module sqlDBModule 'deploy_sql_db.bicep' = {
  name: 'deploy_sql_db'
  params: {
    serverName: 'sql-${solutionSuffix}'
    sqlDBName: 'sqldb-${solutionSuffix}'
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
    tags : tags
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
    tags : tags
  }
  dependsOn:[sqlDBModule,uploadFiles]
}

module hostingplan 'deploy_app_service_plan.bicep' = {
  name: 'deploy_app_service_plan'
  params: {
    solutionLocation: solutionLocation
    HostingPlanName: 'asp-${solutionSuffix}'
    tags : tags
  }
}

module backend_docker 'deploy_backend_docker.bicep' = {
  name: 'deploy_backend_docker'
  params: {
    name: 'api-${solutionSuffix}'
    solutionLocation: solutionLocation
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
      SOLUTION_NAME: solutionSuffix
      APP_ENV: 'Prod'
    }
    tags : tags
  }
  scope: resourceGroup(resourceGroup().name)
}

module frontend_docker 'deploy_frontend_docker.bicep' = {
  name: 'deploy_frontend_docker'
  params: {
    name: 'app-${solutionSuffix}'
    solutionLocation:solutionLocation
    imageTag: imageTag
    acrName: acrName
    appServicePlanId: hostingplan.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    appSettings:{
      APP_API_BASE_URL:backend_docker.outputs.appUrl
    }
    tags : tags
  }
  scope: resourceGroup(resourceGroup().name)
}


@description('Contains Solution Prefix.')
output solutionSuffix string = solutionSuffix

@description('Contains Resource Group Name.')
output resourceGroupName string = resourceGroup().name

@description('Contains Resource Group Location.')
output resourceGroupLocation string = solutionLocation

@description('Contains Environment Name.')
output solutionName string = solutionName

@description('Contains Azure Content Understanding Location.')
output azureContentUnderstandingLocation string = contentUnderstandingLocation

@description('Contains Azure Secondary Location.')
output azureSecondaryLocation string = secondaryLocation

@description('Contains AppInsights Instrumentation Key.')
output appInsightsInstrumentationKey string = backend_docker.outputs.appInsightInstrumentationKey

@description('Contains AI Project Connection String.')
output azureAiProjectConnectionString string = aifoundry.outputs.projectEndpoint

@description('Contains AI Agent API Version.')
output azureAiAgentApiVersion string = azureAiAgentApiVersion

@description('Contains AI Foundry Name Name.')
output azureAiFoundryName string = aifoundry.outputs.aiServicesName

@description('Contains AI Project Name.')
output azureAiProjectName string = aifoundry.outputs.aiProjectName

@description('Contains AI Search Name.')
output azureAiSearchName string = aifoundry.outputs.aiSearchName

@description('Contains AI Search Endpoint.')
output azureAiSearchEndpoint string = aifoundry.outputs.aiSearchTarget

@description('Contains AI Search Index.')
output azureAiSearchIndex string = 'call_transcripts_index'

@description('Contains AI Search Connection Name.')
output azureAiSearchConnectionName string = aifoundry.outputs.aiSearchConnectionName

@description('Contains Azure Cosmos DB Account.')
output azureCosmosDbAccount string = cosmosDBModule.outputs.cosmosAccountName

@description('Contains Azure Cosmos DB Conversations Container.')
output azureCosmosDbConversationsContainer string = 'conversations'

@description('Contains Azure Cosmos DB Database.')
output azureCosmosDbDatabase string = 'db_conversation_history'

@description('Contains Cosmos DB Enable Feedback.')
output azureCOSMOSDB_ENABLE_FEEDBACK string = 'True'

@description('Contains OpenAI Deployment Model.')
output azureOpenaiDeploymentModel string = gptModelName

@description('Contains OpenAI Deployment Capacity.')
output azureOpenaiDeploymentModelCapacity int = gptDeploymentCapacity

@description('Contains OpenAI Endpoint.')
output azureOpenaiENDPOINT string = aifoundry.outputs.aiServicesTarget

@description('Contains OpenAI Model Deployment Type.')
output azureOpenaiModelDeploymentType string = deploymentType

@description('Contains OpenAI Embedding Model.')
output azureOpenaiEmbeddingModel string = embeddingModel

@description('Contains OpenAI Embedding Model Capacity.')
output azureOpenaiEmbeddingModelCapacity int = embeddingDeploymentCapacity

@description('Contains OpenAI API Version.')
output azureOpenaiApiVersion string = azureOpenAIApiVersion

@description('Contains OpenAI Resource.')
output azureOenaiResource string = aifoundry.outputs.aiServicesName

@description('Contains React App Layout Config.')
output reactAppLayoutConfig string = backend_docker.outputs.reactAppLayoutConfig

@description('Contains SQL Database.')
output sqlDatabase string = sqlDBModule.outputs.sqlDbName

@description('Contains SQL DB Server.')
output sqlServer string = sqlDBModule.outputs.sqlServerName

@description('Contains SQL DB User MID.')
output sqlUserMid string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId

@description('Contains Use AI Project Client.')
output useAiProjectClient string = 'False'

@description('To specify whether to Enable or Disable chat history.')
output useChatHistoryEnabled string = 'True'

@description('To specify whether to Enable or Disable Display Chart.')
output displayChartDefault string = 'False'

@description('Contains AI Agent Endpoint.')
output azureAiAgentEndpoint string = aifoundry.outputs.projectEndpoint

@description('Contains Azure AI Agent Model Deployment Name.')
output azureAiAgentModelDeploymentName string = gptModelName

@description('Contains ACR Name.')
output acrName string = acrName

@description('Contains Azure Environment Image Tag.')
output azureEnvImageTag string = imageTag

@description('Contains Existing AI Project Resource ID.')
output azureExistingAiProjectResourceId string = azureExistingAIProjectResourceId

@description('Contains App Insights Connection String.')
output applicationinsightsConnectionString string = aifoundry.outputs.applicationInsightsConnectionString

@description('Contains API App URL.')
output apiAppUrl string = backend_docker.outputs.appUrl

@description('Contains Web App URL.')
output webAppUrl string = frontend_docker.outputs.appUrl
