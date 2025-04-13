// ========== main.bicep ========== //
targetScope = 'resourceGroup'

@minLength(3)
@maxLength(20)
@description('A unique prefix for all resources in this deployment. This should be 3-20 characters long:')
param environmentName string

@minLength(1)
@description('Location for the Content Understanding service deployment:')
@allowed(['swedencentral' 
'australiaeast'
])

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

var uniqueId = toLower(uniqueString(subscription().id, environmentName, resourceGroup().location))
var solutionPrefix = 'km${padLeft(take(uniqueId, 12), 12, '0')}'
var resourceGroupLocation = resourceGroup().location
// var resourceGroupName = resourceGroup().name

var solutionLocation = resourceGroupLocation
var baseUrl = 'https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/'


// ========== Managed Identity ========== //
module managedIdentityModule 'deploy_managed_identity.bicep' = {
  name: 'deploy_managed_identity'
  params: {
    solutionName: solutionPrefix
    solutionLocation: solutionLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

// ==========Key Vault Module ========== //
module kvault 'deploy_keyvault.bicep' = {
  name: 'deploy_keyvault'
  params: {
    solutionName: solutionPrefix
    solutionLocation: resourceGroupLocation
    managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.objectId
  }
  scope: resourceGroup(resourceGroup().name)
}

// ==========AI Foundry and related resources ========== //
module aifoundry 'deploy_ai_foundry.bicep' = {
  name: 'deploy_ai_foundry'
  params: {
    solutionName: solutionPrefix
    solutionLocation: resourceGroupLocation
    keyVaultName: kvault.outputs.keyvaultName
    cuLocation: contentUnderstandingLocation
    deploymentType: deploymentType
    gptModelName: gptModelName
    azureOpenAIApiVersion: azureOpenAIApiVersion
    gptDeploymentCapacity: gptDeploymentCapacity
    embeddingModel: embeddingModel
    embeddingDeploymentCapacity: embeddingDeploymentCapacity
    managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.objectId
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Storage account module ========== //
module storageAccount 'deploy_storage_account.bicep' = {
  name: 'deploy_storage_account'
  params: {
    solutionName: solutionPrefix
    solutionLocation: solutionLocation
    keyVaultName: kvault.outputs.keyvaultName
    managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.objectId
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Cosmos DB module ========== //
module cosmosDBModule 'deploy_cosmos_db.bicep' = {
  name: 'deploy_cosmos_db'
  params: {
    solutionName: solutionPrefix
    solutionLocation: secondaryLocation
    keyVaultName: kvault.outputs.keyvaultName
  }
  scope: resourceGroup(resourceGroup().name)
}

//========== SQL DB module ========== //
module sqlDBModule 'deploy_sql_db.bicep' = {
  name: 'deploy_sql_db'
  params: {
    solutionName: solutionPrefix
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
    solutionName: solutionPrefix
    solutionLocation: secondaryLocation
    baseUrl: baseUrl
    storageAccountName: storageAccount.outputs.storageName
    containerName: storageAccount.outputs.storageContainer
    managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.id
    managedIdentityClientId:managedIdentityModule.outputs.managedIdentityOutput.clientId
    keyVaultName:aifoundry.outputs.keyvaultName
    logAnalyticsWorkspaceResourceName: aifoundry.outputs.logAnalyticsWorkspaceResourceName
    sqlServerName: sqlDBModule.outputs.sqlServerName
    sqlDbName: sqlDBModule.outputs.sqlDbName
    sqlUsers: [
      {
        principalId: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId  // Replace with actual Principal ID
        principalName: managedIdentityModule.outputs.managedIdentityBackendAppOutput.name    // Replace with actual user email or name
        databaseRoles: ['db_datareader', 'db_datawriter']
      }
    ]
  }
}

module hostingplan 'deploy_app_service_plan.bicep' = {
  name: 'deploy_app_service_plan'
  params: {
    solutionName: solutionPrefix
  }
}

module backend_docker 'deploy_backend_docker.bicep'= {
  name: 'deploy_backend_docker'
  params: {
    imageTag: imageTag
    appServicePlanId: hostingplan.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    solutionName: solutionPrefix
    azureOpenAIKey:keyVault.getSecret('AZURE-OPENAI-KEY')
    azureAiProjectConnString:keyVault.getSecret('AZURE-AI-PROJECT-CONN-STRING')
    azureSearchAdminKey:keyVault.getSecret('AZURE-SEARCH-KEY')
    userassignedIdentityId: managedIdentityModule.outputs.managedIdentityBackendAppOutput.id
    aiProjectName: aifoundry.outputs.aiProjectName
    appSettings:{
        AZURE_OPEN_AI_DEPLOYMENT_MODEL:gptModelName
        AZURE_OPEN_AI_ENDPOINT:aifoundry.outputs.aiServicesTarget
        AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
        AZURE_OPENAI_RESOURCE:aifoundry.outputs.aiServicesName
        AZURE_KEY_VAULT_URL: kvault.outputs.keyvaultUri
        USE_CHAT_HISTORY_ENABLED:'True'
        AZURE_COSMOSDB_ACCOUNT: cosmosDBModule.outputs.cosmosAccountName
        AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: cosmosDBModule.outputs.cosmosContainerName
        AZURE_COSMOSDB_DATABASE: cosmosDBModule.outputs.cosmosDatabaseName
        AZURE_COSMOSDB_ENABLE_FEEDBACK:'True'
        SQLDB_DATABASE:sqlDBModule.outputs.sqlDbName
        SQLDB_SERVER: sqlDBModule.outputs.sqlServerName
        SQLDB_USERNAME: sqlDBModule.outputs.sqlDbUser
        SQLDB_USER_MID: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId

        OPENAI_API_VERSION: azureOpenAIApiVersion
        AZURE_AI_SEARCH_ENDPOINT: aifoundry.outputs.aiSearchTarget
        AZURE_AI_SEARCH_INDEX: 'call_transcripts_index'
        USE_AI_PROJECT_CLIENT:'False'
        DISPLAY_CHART_DEFAULT:'True'
      }
  }
  scope: resourceGroup(resourceGroup().name)
}

module frontend_docker 'deploy_frontend_docker.bicep'= {
  name: 'deploy_frontend_docker'
  params: {
    imageTag: imageTag
    appServicePlanId: hostingplan.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    solutionName: solutionPrefix
    appSettings:{
      APP_API_BASE_URL:backend_docker.outputs.appUrl
    }
  }
  scope: resourceGroup(resourceGroup().name)
}

output WEB_APP_URL string = frontend_docker.outputs.appUrl
