// ============================================================================
// Module: Cosmos DB (MongoDB)
// Description: AVM wrapper for Azure Cosmos DB with MongoDB API
// AVM Module: avm/res/document-db/database-account:0.19.0
// WAF: https://learn.microsoft.com/azure/well-architected/service-guides/cosmos-db
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the Cosmos DB account.')
param name string = 'cosmos-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('MongoDB database name.')
param databaseName string = 'default'

@description('MongoDB collections to create.')
param collections array = []

@description('MongoDB server version.')
@allowed(['4.2', '5.0', '6.0', '7.0'])
param serverVersion string = '7.0'

@description('Enable analytical storage (Synapse Link).')
param enableAnalyticalStorage bool = false

@description('Default consistency level.')
@allowed(['Eventual', 'ConsistentPrefix', 'Session', 'BoundedStaleness', 'Strong'])
param consistencyLevel string = 'Session'

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// --- WAF: Monitoring ---
@description('Diagnostic settings for monitoring.')
param diagnosticSettings array = []

// --- WAF: Private Networking ---
@description('Public network access setting.')
param publicNetworkAccess string = 'Enabled'

import { privateEndpointSingleServiceType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. Configuration details for private endpoints. For security reasons, it is recommended to use private endpoints whenever possible.')
param privateEndpoints privateEndpointSingleServiceType[]?

// --- WAF: Redundancy ---
@description('Enable zone redundancy.')
param zoneRedundant bool = false

@description('Enable automatic failover.')
param enableAutomaticFailover bool = false

@description('Optional. HA paired region for multi-region failover when redundancy is enabled.')
param haLocation string = ''

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

// ============================================================================
// AVM Module Deployment
// ============================================================================
module cosmosAccount 'br/public:avm/res/document-db/database-account:0.19.0' = {
  name: take('avm.res.document-db.database-account.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    capabilitiesToAdd: ['EnableMongo']
    serverVersion: serverVersion
    enableAnalyticalStorage: enableAnalyticalStorage
    defaultConsistencyLevel: consistencyLevel
    mongodbDatabases: [
      {
        name: databaseName
        collections: collections
      }
    ]
    diagnosticSettings: !empty(diagnosticSettings) ? diagnosticSettings : []
    networkRestrictions: {
      networkAclBypass: 'AzureServices'
      publicNetworkAccess: publicNetworkAccess
    }
    privateEndpoints: privateEndpoints
    zoneRedundant: zoneRedundant
    enableAutomaticFailover: enableAutomaticFailover
    managedIdentities: managedIdentities
    failoverLocations: zoneRedundant && !empty(haLocation)
      ? [
          { failoverPriority: 0, isZoneRedundant: true, locationName: location }
          { failoverPriority: 1, isZoneRedundant: true, locationName: haLocation }
        ]
      : [
          { locationName: location, failoverPriority: 0, isZoneRedundant: false }
        ]
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the Cosmos DB account.')
output resourceId string = cosmosAccount.outputs.resourceId

@description('Name of the Cosmos DB account.')
output name string = cosmosAccount.outputs.name

@secure()
@description('MongoDB connection string (without credentials — use Key Vault for secrets).')
output connectionString string = cosmosAccount.outputs.primaryReadWriteConnectionString

@description('Endpoint of the Cosmos DB account.')
output endpoint string = 'https://${name}.mongo.cosmos.azure.com:443/'

@description('Database name.')
output databaseName string = databaseName
