// ========== main.bicep ========== //
targetScope = 'resourceGroup'

@minLength(3)
@maxLength(10)
@description('A unique prefix for all resources in this deployment. This should be 3-10 characters long:')
param environmentName string

@minLength(1)
@description('Location for the Content Understanding service deployment:')
@allowed(['West US'
'Sweden Central' 
'Australia East'
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
var gptModelVersion = '2024-02-15-preview'

@minValue(10)
@description('Capacity of the GPT deployment:')
// You can increase this, but capacity is limited per model/region, so you will get errors if you go over
// https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits
param gptDeploymentCapacity int = 100

@minLength(1)
@description('Name of the Text Embedding model to deploy:')
@allowed([
  'text-embedding-ada-002'
])
param embeddingModel string = 'text-embedding-ada-002'


@minValue(10)
@description('Capacity of the Embedding Model deployment')
param embeddingDeploymentCapacity int = 80

param imageTag string = 'latest'

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
    gptModelVersion: gptModelVersion
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
  }
  scope: resourceGroup(resourceGroup().name)
}

//========== Updates to Key Vault ========== //
resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: aifoundry.outputs.keyvaultName
  scope: resourceGroup(resourceGroup().name)
}

//========== Deployment script to upload sample data ========== //
module uploadFiles 'deploy_upload_files_script.bicep' = {
  name : 'deploy_upload_files_script'
  params:{
    solutionLocation: solutionLocation
    baseUrl: baseUrl
    storageAccountName: storageAccount.outputs.storageName
    containerName: storageAccount.outputs.storageContainer
    managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.id
  }
  // dependsOn:[storageAccount,keyVault]
}

//========== Deployment script to process and index data ========== //
module createIndex 'deploy_index_scripts.bicep' = {
  name : 'deploy_index_scripts'
  params:{
    solutionLocation: solutionLocation
    identity:managedIdentityModule.outputs.managedIdentityOutput.id
    baseUrl:baseUrl
    keyVaultName:aifoundry.outputs.keyvaultName
  }
  dependsOn:[keyVault,sqlDBModule,uploadFiles]
}

//========== Azure functions module ========== //
module azureFunctionsCharts 'deploy_azure_function_charts.bicep' = {
  name : 'deploy_azure_function_charts'
  params:{
    imageTag: imageTag
    solutionName: solutionPrefix
    solutionLocation: solutionLocation
    sqlServerName: sqlDBModule.outputs.sqlServerName
    sqlDbName: sqlDBModule.outputs.sqlDbName
    sqlDbUser: sqlDBModule.outputs.sqlDbUser
    sqlDbPwd:keyVault.getSecret('SQLDB-PASSWORD')
    // managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.objectId
  }
  dependsOn:[keyVault]
}

//========== Azure functions module ========== //
module azureragFunctionsRag 'deploy_azure_function_rag.bicep' = {
  name : 'deploy_azure_function_rag'
  params:{
    imageTag: imageTag
    solutionName: solutionPrefix
    solutionLocation: solutionLocation
    azureOpenAIApiKey:keyVault.getSecret('AZURE-OPENAI-KEY')
    azureOpenAIEndpoint:aifoundry.outputs.aiServicesTarget
    azureOpenAIDeploymentModel:gptModelName
    azureSearchAdminKey:keyVault.getSecret('AZURE-SEARCH-KEY')
    azureSearchServiceEndpoint:aifoundry.outputs.aiSearchTarget
    azureOpenAIApiVersion: gptModelVersion //'2024-02-15-preview'
    azureAiProjectConnString:keyVault.getSecret('AZURE-AI-PROJECT-CONN-STRING')
    azureSearchIndex:'call_transcripts_index'
    sqlServerName:sqlDBModule.outputs.sqlServerName
    sqlDbName:sqlDBModule.outputs.sqlDbName
    sqlDbUser:sqlDBModule.outputs.sqlDbUser
    sqlDbPwd:keyVault.getSecret('SQLDB-PASSWORD')
    aiProjectName:aifoundry.outputs.aiProjectName
    // managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.objectId
  }
  dependsOn:[keyVault]
}

module azureFunctionURL 'deploy_azure_function_urls.bicep' = {
  name : 'deploy_azure_function_urls'
  params:{
    solutionName: solutionPrefix
    // identity:managedIdentityModule.outputs.managedIdentityOutput.id
  }
  dependsOn:[azureFunctionsCharts,azureragFunctionsRag]
}

//========== App service module ========== //
module appserviceModule 'deploy_app_service.bicep' = {
  name: 'deploy_app_service'
  params: {
    imageTag: imageTag
    // identity:managedIdentityModule.outputs.managedIdentityOutput.id
    solutionName: solutionPrefix
    // solutionLocation: solutionLocation
    AzureOpenAIEndpoint:aifoundry.outputs.aiServicesTarget
    AzureOpenAIModel: gptModelName //'gpt-4o-mini'
    AzureOpenAIKey:keyVault.getSecret('AZURE-OPENAI-KEY')
    azureOpenAIApiVersion: gptModelVersion //'2024-02-15-preview'
    AZURE_OPENAI_RESOURCE:aifoundry.outputs.aiServicesName
    CHARTS_URL:azureFunctionURL.outputs.functionURLsOutput.charts_function_url
    FILTERS_URL:azureFunctionURL.outputs.functionURLsOutput.filters_function_url
    USE_GRAPHRAG:'False'
    USE_CHAT_HISTORY_ENABLED:'True'
    GRAPHRAG_URL:azureFunctionURL.outputs.functionURLsOutput.graphrag_function_url
    RAG_URL:azureFunctionURL.outputs.functionURLsOutput.rag_function_url
    AZURE_COSMOSDB_ACCOUNT: cosmosDBModule.outputs.cosmosAccountName
    // AZURE_COSMOSDB_ACCOUNT_KEY: keyVault.getSecret('AZURE-COSMOSDB-ACCOUNT-KEY')
    AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: cosmosDBModule.outputs.cosmosContainerName
    AZURE_COSMOSDB_DATABASE: cosmosDBModule.outputs.cosmosDatabaseName
    AZURE_COSMOSDB_ENABLE_FEEDBACK:'True'
  }
  scope: resourceGroup(resourceGroup().name)
  dependsOn:[sqlDBModule]
}
