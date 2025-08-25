@description('Required. Specifies the location for resources.')
param solutionLocation string

@description('Required. Contains KeyVault Name')
param keyVaultName string

@description('Required. Contains Account Name')
param accountName string 
// var accountName = '${ solutionName }-cosmos'
var databaseName = 'db_conversation_history'
var collectionName = 'conversations'

var containers = [
  {
    name: collectionName
    id: collectionName
    partitionKey: '/userId'
  }
]

@allowed([ 'GlobalDocumentDB', 'MongoDB', 'Parse' ])
param kind string = 'GlobalDocumentDB'

param tags object = {}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2022-08-15' = {
  name: accountName
  kind: kind
  location: solutionLocation
  tags: tags
  properties: {
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [
      {
        locationName: solutionLocation
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    databaseAccountOfferType: 'Standard'
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    disableLocalAuth: true
    apiProperties: (kind == 'MongoDB') ? { serverVersion: '4.0' } : {}
    capabilities: [ { name: 'EnableServerless' } ]
  }
}


resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2022-05-15' = {
  name: '${accountName}/${databaseName}'
  properties: {
    resource: { id: databaseName }
  }

  resource list 'containers' = [for container in containers: {
    name: container.name
    properties: {
      resource: {
        id: container.id
        partitionKey: { paths: [ container.partitionKey ] }
      }
      options: {}
    }
  }]

  dependsOn: [
    cosmos
  ]
}

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: keyVaultName
}

resource AZURE_COSMOSDB_ACCOUNT 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-COSMOSDB-ACCOUNT'
  properties: {
    value: cosmos.name
  }
}

resource AZURE_COSMOSDB_ACCOUNT_KEY 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-COSMOSDB-ACCOUNT-KEY'
  properties: {
    value: cosmos.listKeys().primaryMasterKey
  }
}

resource AZURE_COSMOSDB_DATABASE 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-COSMOSDB-DATABASE'
  properties: {
    value: databaseName
  }
}

resource AZURE_COSMOSDB_CONVERSATIONS_CONTAINER 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-COSMOSDB-CONVERSATIONS-CONTAINER'
  properties: {
    value: collectionName
  }
}

resource AZURE_COSMOSDB_ENABLE_FEEDBACK 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-COSMOSDB-ENABLE-FEEDBACK'
  properties: {
    value: 'True'
  }
}

@description('Contains Cosmos Account Name.')
output cosmosAccountName string = cosmos.name

@description('Contains Cosmos DB Name.')
output cosmosDatabaseName string = databaseName

@description('Contains Cosmos Container Name.')
output cosmosContainerName string = collectionName
