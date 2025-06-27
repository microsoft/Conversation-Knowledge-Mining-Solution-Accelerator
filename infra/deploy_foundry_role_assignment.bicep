param principalId string = ''
param roleDefinitionId string
param roleAssignmentName string = ''
param aiServicesName string
param userassignedIdentityId string = ''

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiServicesName
}

resource roleAssignmentToFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(aiServicesName) && !empty(principalId)) {
  name: roleAssignmentName
  scope: aiServices
  properties: {
    roleDefinitionId: roleDefinitionId
    principalId: principalId
  }
}

resource roleAssignmentToManagedIdentity 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(userassignedIdentityId)) {
  name: roleAssignmentName
  scope: aiServices
  properties: {
    roleDefinitionId: roleDefinitionId
    principalId: userassignedIdentityId
    principalType: 'ServicePrincipal'
  }
}
