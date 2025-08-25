// ========== Managed Identity ========== //
targetScope = 'resourceGroup'

@minLength(3)
@maxLength(16)
@description('Required. Contains Solution Name.')
param solutionName string

@description('Required. Specifies the location for resources.')
param solutionLocation string

@description('Required. Contains MI Name.')
param miName string 

@description('Optional. The tags to apply to all deployed Azure resources.')
param tags object = {}

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: miName
  location: solutionLocation
  tags: tags
}

@description('This is the built-in owner role. See https://docs.microsoft.com/azure/role-based-access-control/built-in-roles#owner')
resource ownerRoleDefinition 'Microsoft.Authorization/roleDefinitions@2018-01-01-preview' existing = {
  scope: resourceGroup()
  name: '8e3af657-a8ff-443c-a75c-2fe8c4bcb635'
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, managedIdentity.id, ownerRoleDefinition.id)
  properties: {
    principalId: managedIdentity.properties.principalId
    roleDefinitionId:  ownerRoleDefinition.id
    principalType: 'ServicePrincipal' 
  }
}

resource managedIdentityBackendApp 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${solutionName}-backend-app-mi'
  location: solutionLocation
  tags: {
    app: solutionName
    location: solutionLocation
  }
}

@description('Contains Managed Identity Object details.')
output managedIdentityOutput object = {
  id: managedIdentity.id
  objectId: managedIdentity.properties.principalId
  clientId: managedIdentity.properties.clientId
  name: miName
}

@description('Contains Managed Identity Backend App Output details..')
output managedIdentityBackendAppOutput object = {
  id: managedIdentityBackendApp.id
  objectId: managedIdentityBackendApp.properties.principalId
  clientId: managedIdentityBackendApp.properties.clientId
  name: managedIdentityBackendApp.name
}
