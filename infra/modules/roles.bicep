param openaiName string
param searchName string
param storageName string
param cosmosName string
param cuName string
param backendPrincipalId string

@description('Principal ID of the deploying user (for local script access)')
param deployerPrincipalId string = ''

// ========== Role Definition IDs ========== //
var roles = {
  cognitiveServicesOpenAIUser: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  cognitiveServicesUser: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  azureAIDeveloper: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '64702f94-c441-49e6-a78b-ef80e0188fee')
  searchIndexDataContributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  searchServiceContributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
  storageBlobDataContributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  cosmosDBDataContributor: '00000000-0000-0000-0000-000000000002'
}

// ========== Backend App (ServicePrincipal) Roles ========== //

resource openaiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openai.id, backendPrincipalId, roles.cognitiveServicesOpenAIUser)
  scope: openai
  properties: {
    roleDefinitionId: roles.cognitiveServicesOpenAIUser
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource searchRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, backendPrincipalId, roles.searchIndexDataContributor)
  scope: search
  properties: {
    roleDefinitionId: roles.searchIndexDataContributor
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource storageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, backendPrincipalId, roles.storageBlobDataContributor)
  scope: storage
  properties: {
    roleDefinitionId: roles.storageBlobDataContributor
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource cosmosRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (cosmosName != '') {
  parent: cosmos
  name: guid(cosmos.id, backendPrincipalId, roles.cosmosDBDataContributor)
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/${roles.cosmosDBDataContributor}'
    principalId: backendPrincipalId
    scope: cosmos.id
  }
}

resource cuRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cu.id, backendPrincipalId, roles.cognitiveServicesUser)
  scope: cu
  properties: {
    roleDefinitionId: roles.cognitiveServicesUser
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ========== Deploying User Roles ========== //

resource deployerAiDeveloperRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(openai.id, deployerPrincipalId, roles.azureAIDeveloper)
  scope: openai
  properties: {
    roleDefinitionId: roles.azureAIDeveloper
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

resource deployerOpenaiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(openai.id, deployerPrincipalId, roles.cognitiveServicesOpenAIUser)
  scope: openai
  properties: {
    roleDefinitionId: roles.cognitiveServicesOpenAIUser
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

resource deployerSearchRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(search.id, deployerPrincipalId, roles.searchIndexDataContributor)
  scope: search
  properties: {
    roleDefinitionId: roles.searchIndexDataContributor
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

resource deployerSearchContribRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(search.id, deployerPrincipalId, roles.searchServiceContributor)
  scope: search
  properties: {
    roleDefinitionId: roles.searchServiceContributor
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

resource deployerStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(storage.id, deployerPrincipalId, roles.storageBlobDataContributor)
  scope: storage
  properties: {
    roleDefinitionId: roles.storageBlobDataContributor
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

resource deployerCuRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(cu.id, deployerPrincipalId, roles.cognitiveServicesUser)
  scope: cu
  properties: {
    roleDefinitionId: roles.cognitiveServicesUser
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

// ========== Existing resource references ========== //
resource openai 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openaiName
}

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchName
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageName
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosName
}

resource cu 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: cuName
}
