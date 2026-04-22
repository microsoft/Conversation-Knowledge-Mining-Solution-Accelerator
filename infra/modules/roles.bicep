param openaiName string
param searchName string
param storageName string
param cosmosName string
param cuName string
param backendPrincipalId string

// Cognitive Services OpenAI User — allows chat completions + embeddings
resource openaiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openaiName, backendPrincipalId, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: openai
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor — read/write search index
resource searchRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchName, backendPrincipalId, '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Blob Data Contributor — upload/read blobs
resource storageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageName, backendPrincipalId, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB Built-in Data Contributor (only if Cosmos is deployed)
resource cosmosRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (cosmosName != '') {
  parent: cosmos
  name: guid(cosmosName, backendPrincipalId, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: backendPrincipalId
    scope: cosmos.id
  }
}

// Cognitive Services User — for Content Understanding
resource cuRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cuName, backendPrincipalId, 'a97b65f3-24c7-4388-baec-2e87135dc908')
  scope: cu
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Existing resource references
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
