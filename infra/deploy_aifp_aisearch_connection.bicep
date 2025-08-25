@description('Required. Contains existing AI Project Name')
param existingAIProjectName string

@description('Required. Contains existing AI Services Name')
param existingAIServicesName string

@description('Required. Contains AI Search Name')
param aiSearchName string

@description('Required. Contains AI Search Resource ID')
param aiSearchResourceId string

@description('Required. Contains AI Search Location')
param aiSearchLocation string

@description('Required. Contains AI Search Connection Name')
param aiSearchConnectionName string

resource projectAISearchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  name: '${existingAIServicesName}/${existingAIProjectName}/${aiSearchConnectionName}'
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${aiSearchName}.search.windows.net'
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: aiSearchResourceId
      location: aiSearchLocation
    }
  }
}
