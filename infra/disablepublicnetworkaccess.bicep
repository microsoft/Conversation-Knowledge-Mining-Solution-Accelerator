param solutionLocation string = 'eastus2'
param sqlServerName string = 'km4bpxf4ybvyr2-sql-server'
param cosmosDBAccountName string = 'km4bpxf4ybvyr2-cosmos'
param storageAccountName string = 'km4bpxf4ybvyr2storage'
param storageAccountHubName string = 'km4bpxf4ybvyr2-kv'
param keyVaultName string = 'km4bpxf4ybvyr2-kv'

// Disable public access after Private Endpoints are created
resource disableSqlPublicAccess 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: sqlServerName
  properties: {
    publicNetworkAccess: 'Disabled'
  }
  location: solutionLocation
}

resource disableCosmosPublicAccess 'Microsoft.DocumentDB/databaseAccounts@2022-08-15' = {
  name: cosmosDBAccountName
  location:solutionLocation
  properties: {
    publicNetworkAccess: 'Disabled'
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: solutionLocation
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
  }
}

resource disableStoragePublicAccess 'Microsoft.Storage/storageAccounts@2021-06-01' = {
  name: storageAccountName
  properties: {
    publicNetworkAccess: 'Disabled'
  }
  location: solutionLocation
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
}
resource disableHubStoragePublicAccess 'Microsoft.Storage/storageAccounts@2021-06-01' = {
  name: storageAccountHubName
  properties: {
    publicNetworkAccess: 'Disabled'
  }
  location: solutionLocation
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
}

resource disableKeyVaultPublicAccess 'Microsoft.KeyVault/vaults@2021-10-01' = {
  name: keyVaultName
  properties: {
    publicNetworkAccess: 'Disabled'
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    accessPolicies: []
  }
  location: solutionLocation
}
