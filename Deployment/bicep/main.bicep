// ========== main.bicep ========== //
targetScope = 'resourceGroup'

@minLength(3)
@maxLength(6)
@description('Prefix Name')
param solutionPrefix string

@description('other Location')
param otherLocation string

param imageTag string = 'latest'
// @description('Fabric Workspace Id if you have one, else leave it empty. ')
// param fabricWorkspaceId string

var resourceGroupLocation = resourceGroup().location
var resourceGroupName = resourceGroup().name

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

module aifoundry 'deploy_ai_foundry.bicep' = {
  name: 'deploy_ai_foundry'
  params: {
    solutionName: solutionPrefix
    solutionLocation: resourceGroupLocation
    managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.objectId
  }
  scope: resourceGroup(resourceGroup().name)
}


// ========== Storage Account Module ========== //
module storageAccount 'deploy_storage_account.bicep' = {
  name: 'deploy_storage_account'
  params: {
    solutionName: solutionPrefix
    solutionLocation: solutionLocation
    keyVaultName: aifoundry.outputs.keyvaultName
    managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.objectId
  }
  scope: resourceGroup(resourceGroup().name)
}

module cosmosDBModule 'deploy_cosmos_db.bicep' = {
  name: 'deploy_cosmos_db'
  params: {
    solutionName: solutionPrefix
    solutionLocation: otherLocation
    keyVaultName: aifoundry.outputs.keyvaultName
  }
  scope: resourceGroup(resourceGroup().name)
}

//========== SQL DB Module ========== //
module sqlDBModule 'deploy_sql_db.bicep' = {
  name: 'deploy_sql_db'
  params: {
    solutionName: solutionPrefix
    solutionLocation: otherLocation
    keyVaultName: aifoundry.outputs.keyvaultName
  }
  scope: resourceGroup(resourceGroup().name)
}

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: aifoundry.outputs.keyvaultName
  scope: resourceGroup(resourceGroup().name)
}

module uploadFiles 'deploy_upload_files_script.bicep' = {
  name : 'deploy_upload_files_script'
  params:{
    solutionLocation: solutionLocation
    keyVaultName: aifoundry.outputs.keyvaultName
    baseUrl: baseUrl
    storageAccountName: storageAccount.outputs.storageName
    containerName: storageAccount.outputs.storageContainer
    managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.id
  }
  dependsOn:[storageAccount,keyVault]
}

module createIndex 'deploy_index_scripts.bicep' = {
  name : 'deploy_index_scripts'
  params:{
    solutionLocation: solutionLocation
    identity:managedIdentityModule.outputs.managedIdentityOutput.id
    baseUrl:baseUrl
    keyVaultName:aifoundry.outputs.keyvaultName
  }
  dependsOn:[aifoundry,keyVault,sqlDBModule,uploadFiles]
}

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
    managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.objectId
  }
  dependsOn:[sqlDBModule,keyVault]
}

module azureragFunctionsRag 'deploy_azure_function_rag.bicep' = {
  name : 'deploy_azure_function_rag'
  params:{
    imageTag: imageTag
    solutionName: solutionPrefix
    solutionLocation: solutionLocation
    azureOpenAIApiKey:keyVault.getSecret('AZURE-OPENAI-KEY')
    azureOpenAIEndpoint:aifoundry.outputs.aiServicesTarget
    azureSearchAdminKey:keyVault.getSecret('AZURE-SEARCH-KEY')
    azureSearchServiceEndpoint:aifoundry.outputs.aiSearchTarget
    azureOpenAIApiVersion:'2024-02-15-preview'
    azureSearchIndex:'call_transcripts_index'
    sqlServerName:sqlDBModule.outputs.sqlServerName
    sqlDbName:sqlDBModule.outputs.sqlDbName
    sqlDbUser:sqlDBModule.outputs.sqlDbUser
    sqlDbPwd:keyVault.getSecret('SQLDB-PASSWORD')
    managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.objectId
  }
  dependsOn:[aifoundry,sqlDBModule,keyVault]
}

module azureFunctionURL 'deploy_azure_function_urls.bicep' = {
  name : 'deploy_azure_function_urls'
  params:{
    solutionName: solutionPrefix
    identity:managedIdentityModule.outputs.managedIdentityOutput.id
  }
  dependsOn:[azureFunctionsCharts,azureragFunctionsRag]
}

module appserviceModule 'deploy_app_service.bicep' = {
  name: 'deploy_app_service'
  params: {
    imageTag: imageTag
    identity:managedIdentityModule.outputs.managedIdentityOutput.id
    solutionName: solutionPrefix
    solutionLocation: solutionLocation
    AzureOpenAIEndpoint:aifoundry.outputs.aiServicesTarget
    AzureOpenAIModel:'gpt-4o-mini'
    AzureOpenAIKey:keyVault.getSecret('AZURE-OPENAI-KEY')
    azureOpenAIApiVersion:'2024-02-15-preview'
    AZURE_OPENAI_RESOURCE:aifoundry.outputs.aiServicesName
    CHARTS_URL:azureFunctionURL.outputs.functionURLsOutput.charts_function_url
    FILTERS_URL:azureFunctionURL.outputs.functionURLsOutput.filters_function_url
    USE_GRAPHRAG:'False'
    USE_CHAT_HISTORY_ENABLED:'True'
    GRAPHRAG_URL:azureFunctionURL.outputs.functionURLsOutput.graphrag_function_url
    RAG_URL:azureFunctionURL.outputs.functionURLsOutput.rag_function_url
    AZURE_COSMOSDB_ACCOUNT: cosmosDBModule.outputs.cosmosAccountName
    AZURE_COSMOSDB_ACCOUNT_KEY: keyVault.getSecret('AZURE-COSMOSDB-ACCOUNT-KEY')
    AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: cosmosDBModule.outputs.cosmosContainerName
    AZURE_COSMOSDB_DATABASE: cosmosDBModule.outputs.cosmosDatabaseName
    AZURE_COSMOSDB_ENABLE_FEEDBACK:'True'
  }
  scope: resourceGroup(resourceGroup().name)
  dependsOn:[aifoundry,cosmosDBModule,sqlDBModule,azureFunctionURL]
}
