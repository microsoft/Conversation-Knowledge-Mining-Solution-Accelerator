@description('Name of the existing Azure AI Services account')
param aiServicesName string

@description('Name of the existing AI Project under the AI Services account')
param aiProjectName string

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiServicesName
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  name: aiProjectName
  parent: aiServices
}



// Outputs: AI Services Account
output location string = aiServices.location
output skuName string = aiServices.sku.name
output kind string = aiServices.kind
output allowProjectManagement bool = aiServices.properties.allowProjectManagement
output customSubDomainName string = aiServices.properties.customSubDomainName
output publicNetworkAccess string = aiServices.properties.publicNetworkAccess
output defaultNetworkAction string = aiServices.properties.networkAcls.defaultAction
output ipRules array = aiServices.properties.networkAcls.ipRules
output vnetRules array = aiServices.properties.networkAcls.virtualNetworkRules

// Outputs: AI Project

output projectLocation string = aiProject.location
output projectKind string = aiProject.kind
output projectProvisioningState string = aiProject.properties.provisioningState
// output projectDisplayName string = aiProject.properties.displayName
// output projectDescription string = aiProject.properties.description
