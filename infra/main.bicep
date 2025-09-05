// ========== main.bicep ========== //
targetScope = 'resourceGroup'
//var abbrs = loadJsonContent('./abbreviations.json')
@minLength(3)
@maxLength(16)
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
@description('Optional created by user name')
param createdBy string = empty(deployer().userPrincipalName) ? '' : split(deployer().userPrincipalName, '@')[0]
// ========== Resource Group Tag ========== //
resource resourceGroupTags 'Microsoft.Resources/tags@2021-04-01' = {
  name: 'default'
  properties: {
    tags: {
      ... tags
      TemplateName: 'KM Generic'
      CreatedBy: createdBy
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

@description('Contains Solution Name.')
output SOLUTION_NAME string = solutionSuffix

@description('Contains Resource Group Name.')
output RESOURCE_GROUP_NAME string = resourceGroup().name

@description('Contains Resource Group Location.')
output RESOURCE_GROUP_LOCATION string = solutionLocation

@description('Contains Azure Content Understanding Location.')
output AZURE_CONTENT_UNDERSTANDING_LOCATION string = contentUnderstandingLocation

@description('Contains Azure Secondary Location.')
output AZURE_SECONDARY_LOCATION string = secondaryLocation

@description('Contains Application Insights Instrumentation Key.')
output APPINSIGHTS_INSTRUMENTATIONKEY string = backend_docker.outputs.appInsightInstrumentationKey

@description('Contains AI Project Connection String.')
output AZURE_AI_PROJECT_CONN_STRING string = aifoundry.outputs.projectEndpoint


@description('Contains Azure AI Agent API Version.')
output AZURE_AI_AGENT_API_VERSION string = azureAiAgentApiVersion

@description('Contains Azure AI Foundry service name.')
output AZURE_AI_FOUNDRY_NAME string = aifoundry.outputs.aiServicesName

@description('Contains Azure AI Project name.')
output AZURE_AI_PROJECT_NAME string = aifoundry.outputs.aiProjectName

@description('Contains Azure AI Search service name.')
output AZURE_AI_SEARCH_NAME string = aifoundry.outputs.aiSearchName

@description('Contains Azure AI Search endpoint URL.')
output AZURE_AI_SEARCH_ENDPOINT string = aifoundry.outputs.aiSearchTarget

@description('Contains Azure AI Search index name.')
output AZURE_AI_SEARCH_INDEX string = 'call_transcripts_index'

@description('Contains Azure AI Search connection name.')
output AZURE_AI_SEARCH_CONNECTION_NAME string = aifoundry.outputs.aiSearchConnectionName

@description('Contains Azure Cosmos DB account name.')
output AZURE_COSMOSDB_ACCOUNT string = cosmosDBModule.outputs.cosmosAccountName

@description('Contains Azure Cosmos DB conversations container name.')
output AZURE_COSMOSDB_CONVERSATIONS_CONTAINER string = 'conversations'

@description('Contains Azure Cosmos DB database name.')
output AZURE_COSMOSDB_DATABASE string = 'db_conversation_history'

@description('Contains Azure Cosmos DB feedback enablement setting.')
output AZURE_COSMOSDB_ENABLE_FEEDBACK string = 'True'

@description('Contains Azure OpenAI deployment model name.')
output AZURE_OPENAI_DEPLOYMENT_MODEL string = gptModelName

@description('Contains Azure OpenAI deployment model capacity.')
output AZURE_OPENAI_DEPLOYMENT_MODEL_CAPACITY int = gptDeploymentCapacity

@description('Contains Azure OpenAI endpoint URL.')
output AZURE_OPENAI_ENDPOINT string = aifoundry.outputs.aiServicesTarget

@description('Contains Azure OpenAI model deployment type.')
output AZURE_OPENAI_MODEL_DEPLOYMENT_TYPE string = deploymentType

@description('Contains Azure OpenAI embedding model name.')
output AZURE_OPENAI_EMBEDDING_MODEL string = embeddingModel

@description('Contains Azure OpenAI embedding model capacity.')
output AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY int = embeddingDeploymentCapacity

@description('Contains Azure OpenAI API version.')
output AZURE_OPENAI_API_VERSION string = azureOpenAIApiVersion

@description('Contains Azure OpenAI resource name.')
output AZURE_OPENAI_RESOURCE string = aifoundry.outputs.aiServicesName

@description('Contains React app layout configuration.')
output REACT_APP_LAYOUT_CONFIG string = backend_docker.outputs.reactAppLayoutConfig

@description('Contains SQL database name.')
output SQLDB_DATABASE string = sqlDBModule.outputs.sqlDbName

@description('Contains SQL server name.')
output SQLDB_SERVER string = sqlDBModule.outputs.sqlServerName

@description('Contains SQL database user managed identity client ID.')
output SQLDB_USER_MID string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId

@description('Contains AI project client usage setting.')
output USE_AI_PROJECT_CLIENT string = 'False'

@description('Contains chat history enablement setting.')
output USE_CHAT_HISTORY_ENABLED string = 'True'

@description('Contains default chart display setting.')
output DISPLAY_CHART_DEFAULT string = 'False'

@description('Contains Azure AI Agent endpoint URL.')
output AZURE_AI_AGENT_ENDPOINT string = aifoundry.outputs.projectEndpoint

@description('Contains Azure AI Agent model deployment name.')
output AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME string = gptModelName

@description('Contains Azure Container Registry name.')
output ACR_NAME string = acrName

@description('Contains Azure environment image tag.')
output AZURE_ENV_IMAGETAG string = imageTag

@description('Contains existing AI project resource ID.')
output AZURE_EXISTING_AI_PROJECT_RESOURCE_ID string = azureExistingAIProjectResourceId

@description('Contains Application Insights connection string.')
output APPLICATIONINSIGHTS_CONNECTION_STRING string = aifoundry.outputs.applicationInsightsConnectionString

@description('Contains API application URL.')
output API_APP_URL string = backend_docker.outputs.appUrl

@description('Contains web application URL.')
output WEB_APP_URL string = frontend_docker.outputs.appUrl
