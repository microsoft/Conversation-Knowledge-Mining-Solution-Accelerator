@description('Required. Name of the existing Azure AI Services account')
param aiServicesName string

@description('Required. Name of the existing AI Project under the AI Services account')
param aiProjectName string

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiServicesName
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  name: aiProjectName
  parent: aiServices
}



// Outputs: AI Services Account
@description('Contains Service Location.')
output location string = aiServices.location

@description('Contains SKU Name.')
output skuName string = aiServices.sku.name

@description('Contains Kind of Service.')
output kind string = aiServices.kind

@description('Specifies whether to Enable or Disable Project Management.')
output allowProjectManagement bool = aiServices.properties.allowProjectManagement

@description('Contains Custom Sub Domain Name.')
output customSubDomainName string = aiServices.properties.customSubDomainName

@description('Contains Properties of Public Network Access.')
output publicNetworkAccess string = aiServices.properties.publicNetworkAccess

@description('Contains Default Network Action.')
output defaultNetworkAction string = aiServices.properties.networkAcls.defaultAction

@description('Contains the IP Rules.')
output ipRules array = aiServices.properties.networkAcls.ipRules

@description('Contains VNET Rules.')
output vnetRules array = aiServices.properties.networkAcls.virtualNetworkRules

// Outputs: AI Project
@description('Contains Location of Project.')
output projectLocation string = aiProject.location

@description('Contains Kind of Project.')
output projectKind string = aiProject.kind

@description('Contains Project Provisioning State.')
output projectProvisioningState string = aiProject.properties.provisioningState
// output projectDisplayName string = aiProject.properties.displayName
// output projectDescription string = aiProject.properties.description
