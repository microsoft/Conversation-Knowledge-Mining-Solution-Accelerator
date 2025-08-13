@description('Optional. Contains Principle ID.')
param principalId string = ''

@description('Required. Contains Role Definition ID.')
param roleDefinitionId string

@description('Optional. Contains Role Assignment Name.')
param roleAssignmentName string = ''

@description('Required. Contains AI Services Name.')
param aiServicesName string

@description('Optional. Contains AI Project Name.')
param aiProjectName string = ''

@description('Optional. Contains AI Location.')
param aiLocation string=''

@description('Optional. Contains AI Kind.')
param aiKind string=''

@description('Optional. Contains AI SKU Name.')
param aiSkuName string=''

@description('Optional. Whether to Enable or Disable System Assigned Identity.')
param enableSystemAssignedIdentity bool = false

@description('Optional. Contains Custom Sub Domain Name.')
param customSubDomainName string = ''

@description('Optional. Contains Public Network Access.')
param publicNetworkAccess string = ''

@description('Optional. Contains Default Network Action.')
param defaultNetworkAction string = ''

@description('Required. Contains VNET Rules.')
param vnetRules array = []

@description('Required. Contains IP Rules.')
param ipRules array = []

@description('Required. Contains AI Model Deployments.')
param aiModelDeployments array = []

@description('Optional. Tags to be applied to the resources.')
param tags object = {}

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = if (!enableSystemAssignedIdentity) {
  name: aiServicesName
}

resource aiServicesWithIdentity 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = if (enableSystemAssignedIdentity) {
  name: aiServicesName
  location: aiLocation
  kind: aiKind
  sku: {
    name: aiSkuName
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: customSubDomainName 
    networkAcls: {
      defaultAction: defaultNetworkAction
      virtualNetworkRules: vnetRules
      ipRules: ipRules
    }
    publicNetworkAccess: publicNetworkAccess
  }
  tags : tags
}

@batchSize(1)
resource aiServicesDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = [for aiModeldeployment in aiModelDeployments: if (!empty(aiModelDeployments)) {
  parent: aiServicesWithIdentity
  name: aiModeldeployment.name
  properties: {
    model: {
      format: 'OpenAI'
      name: aiModeldeployment.model
    }
    raiPolicyName: aiModeldeployment.raiPolicyName
  }
  sku:{
    name: aiModeldeployment.sku.name
    capacity: aiModeldeployment.sku.capacity
  }
}]

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = if (!empty(aiProjectName) && !enableSystemAssignedIdentity) {
  name: aiProjectName
  parent: aiServices
}

resource aiProjectWithIdentity 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = if (!empty(aiProjectName) && enableSystemAssignedIdentity) {
  name: aiProjectName
  parent: aiServicesWithIdentity
  location: aiLocation
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
  tags : tags
}

// Role Assignment to AI Services
resource roleAssignmentToFoundryExisting 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableSystemAssignedIdentity) {
  name: roleAssignmentName
  scope: aiServicesWithIdentity
  properties: {
    roleDefinitionId: roleDefinitionId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource roleAssignmentToFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!enableSystemAssignedIdentity) {
  name: roleAssignmentName
  scope: aiServices
  properties: {
    roleDefinitionId: roleDefinitionId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// ========== Outputs ==========

output aiServicesPrincipalId string = enableSystemAssignedIdentity
  ? aiServicesWithIdentity.identity.principalId
  : aiServices.identity.principalId

output aiProjectPrincipalId string = !empty(aiProjectName)
  ? (enableSystemAssignedIdentity
      ? aiProjectWithIdentity.identity.principalId
      : aiProject.identity.principalId)
  : ''
