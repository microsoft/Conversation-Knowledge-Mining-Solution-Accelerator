param existingAIProjectName string
param existingAIServicesName string
param aiSearchName string
param aiSearchResourceId string
param aiSearchLocation string
param solutionName string

resource projectAISearchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  name: '${existingAIServicesName}/${existingAIProjectName}/myVectorStoreProjectConnectionName-${solutionName}'
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
