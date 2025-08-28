@description('Required. Specifies the location for resources.')
param solutionLocation string

@description('Required. Contains ID of Managed Identity.')
param managedIdentityObjectId string

@description('Optional. Tags to be applied to the resources.')
param tags object = {}

param keyvaultName string

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' = {
  name: keyvaultName
  location: solutionLocation
  properties: {
    createMode: 'default'
    accessPolicies: [
      {        
        objectId: managedIdentityObjectId        
        permissions: {
          certificates: [
            'all'
          ]
          keys: [
            'all'
          ]
          secrets: [
            'all'
          ]
          storage: [
            'all'
          ]
        }
        tenantId: subscription().tenantId
      }
    ]
    enabledForDeployment: true
    enabledForDiskEncryption: true
    enabledForTemplateDeployment: true
    enableRbacAuthorization: true
    publicNetworkAccess: 'enabled'
    // networkAcls: {
    //   bypass: 'AzureServices'
    //   defaultAction: 'Deny'
    // }
    sku: {
      family: 'A'
      name: 'standard'
    }
    softDeleteRetentionInDays: 7
    tenantId: subscription().tenantId
  }
  tags : tags
}

@description('This is the built-in Key Vault Administrator role.')
resource kvAdminRole 'Microsoft.Authorization/roleDefinitions@2018-01-01-preview' existing = {
  scope: resourceGroup()
  name: '00482a5a-887f-4fb3-b363-3b7fe8e74483'
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, managedIdentityObjectId, kvAdminRole.id)
  properties: {
    principalId: managedIdentityObjectId
    roleDefinitionId:kvAdminRole.id
    principalType: 'ServicePrincipal' 
  }
}

@description('Contains KeyVault Name.')
output keyvaultName string = keyvaultName

@description('Contains KeyVault ID.')
output keyvaultId string = keyVault.id

@description('Contains KeyVault URI.')
output keyvaultUri string = keyVault.properties.vaultUri
