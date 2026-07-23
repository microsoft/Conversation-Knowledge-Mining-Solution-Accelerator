param name string
param location string
param tags object
param databaseName string

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: name
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      { name: 'EnableServerless' }
    ]
    publicNetworkAccess: 'Enabled'
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// Chat sessions container
resource chatSessions 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'chat_sessions'
  properties: {
    resource: {
      id: 'chat_sessions'
      partitionKey: { paths: ['/user_id'], kind: 'Hash' }
    }
  }
}

// Chat messages container
resource chatMessages 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'chat_messages'
  properties: {
    resource: {
      id: 'chat_messages'
      partitionKey: { paths: ['/session_id'], kind: 'Hash' }
    }
  }
}

// Document insights container
resource insights 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'document_insights'
  properties: {
    resource: {
      id: 'document_insights'
      partitionKey: { paths: ['/dataset_id'], kind: 'Hash' }
    }
  }
}

// Enrichment cache container
resource enrichmentCache 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'enrichment_cache'
  properties: {
    resource: {
      id: 'enrichment_cache'
      partitionKey: { paths: ['/doc_hash'], kind: 'Hash' }
    }
  }
}

output endpoint string = cosmosAccount.properties.documentEndpoint
output name string = cosmosAccount.name
output id string = cosmosAccount.id
