// ========== Storage Account ========== //
targetScope = 'resourceGroup'

@description('Required. Specifies the location for resources.')
param solutionLocation string

@description('Required. Contains Storage Account Name.')
param saName string 

@description('Required. Contains KeyVault Name.')
param keyVaultName string

@description('Required. Contains Managed Identity Object ID.')
param managedIdentityObjectId string

@description('Optional. Tags to be applied to the resources.')
param tags object = {}

resource storageAccounts_resource 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: saName
  location: solutionLocation
  sku: {
    name: 'Standard_LRS'
    tier: 'Standard'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    isHnsEnabled: true
    networkAcls: {
      bypass: 'AzureServices'
      virtualNetworkRules: []
      ipRules: []
      defaultAction: 'Allow'
    }
    supportsHttpsTrafficOnly: true
    encryption: {
      services: {
        file: {
          keyType: 'Account'
          enabled: true
        }
        blob: {
          keyType: 'Account'
          enabled: true
        }
      }
      keySource: 'Microsoft.Storage'
    }
    accessTier: 'Hot'
  }
  tags : tags
}

resource storageAccounts_default 'Microsoft.Storage/storageAccounts/blobServices@2022-09-01' = {
  parent: storageAccounts_resource
  name: 'default'
  properties: {
    cors: {
      corsRules: []
    }
    deleteRetentionPolicy: {
      allowPermanentDelete: false
      enabled: false
    }
  }
}


resource storageAccounts_default_data 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  parent: storageAccounts_default
  name: 'data'
  properties: {
    defaultEncryptionScope: '$account-encryption-key'
    denyEncryptionScopeOverride: false
    publicAccess: 'None'
  }
}

// resource storageAccounts_default_input 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
//   parent: storageAccounts_default
//   name: 'graphrag'
//   properties: {
//     defaultEncryptionScope: '$account-encryption-key'
//     denyEncryptionScopeOverride: false
//     publicAccess: 'None'
//   }
//   dependsOn: [
//     storageAccounts_resource
//   ]
// }

@description('This is the built-in Storage Blob Data Contributor.')
resource blobDataContributor 'Microsoft.Authorization/roleDefinitions@2018-01-01-preview' existing = {
  scope: resourceGroup()
  name: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, managedIdentityObjectId, blobDataContributor.id)
  properties: {
    principalId: managedIdentityObjectId
    roleDefinitionId:blobDataContributor.id
    principalType: 'ServicePrincipal' 
  }
}


var storageAccountKeys = listKeys(storageAccounts_resource.id, '2021-04-01')
// var storageAccountString = 'DefaultEndpointsProtocol=https;AccountName=${storageAccounts_resource.name};AccountKey=${storageAccounts_resource.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: keyVaultName
}

resource adlsAccountNameEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'ADLS-ACCOUNT-NAME'
  properties: {
    value: saName
  }
  tags : tags
}

resource adlsAccountContainerEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'ADLS-ACCOUNT-CONTAINER'
  properties: {
    value: 'data'
  }
  tags : tags
}

resource adlsAccountKeyEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'ADLS-ACCOUNT-KEY'
  properties: {
    value: storageAccountKeys.keys[0].value
  }
  tags : tags
}

@description('Contains Storage Name.')
output storageName string = saName

@description('Contains Storage Container Name.')
output storageContainer string = 'data'
// output storageAccountOutput object = {
//   id: storageAccounts_resource.id
//   name: saName
//   uri: storageAccounts_resource.properties.primaryEndpoints.web  
//   dfs: storageAccounts_resource.properties.primaryEndpoints.dfs
//   storageAccountName:saName
//   key:storageAccountKeys.keys[0].value
//   connectionString:storageAccountString
//   dataContainer:storageAccounts_default_data.name
// }

