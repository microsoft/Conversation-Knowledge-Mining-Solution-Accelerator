// ============================================================================
// Module: Azure App Configuration (AVM)
// ============================================================================

@description('Solution name used for naming convention.')
param solutionName string

@description('Name of the App Configuration store.')
param name string = 'appcs-${solutionName}'

@description('Azure region for deployment.')
param location string

@description('Resource tags.')
param tags object = {}

@description('Enable Azure telemetry collection.')
param enableTelemetry bool = true

@description('SKU for the configuration store.')
@allowed(['Free', 'Standard'])
param sku string = 'Standard'

@description('Disable local (key-based) authentication.')
param disableLocalAuth bool = true

@description('Enable purge protection.')
param enablePurgeProtection bool = false

@description('Soft delete retention in days.')
param softDeleteRetentionInDays int = 7

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

@description('Role assignments.')
param roleAssignments array = []

@description('Key-value pairs to store in the configuration.')
param keyValues array = []

@description('Optional. Public network access override. Set to Enabled to allow ARM keyValues writes during deploy.')
param publicNetworkAccess string = 'Enabled'

import { privateEndpointSingleServiceType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. Configuration details for private endpoints. For security reasons, it is recommended to use private endpoints whenever possible.')
param privateEndpoints privateEndpointSingleServiceType[]?

@description('Optional. Diagnostic settings for the resource.')
param diagnosticSettings array?

@description('Optional. The replica location for Log Analytics Workspace, if redundancy is enabled.')
param replicaLocations array = []

// ============================================================================
// App Configuration (AVM)
// ============================================================================

module configStore 'br/public:avm/res/app-configuration/configuration-store:0.9.2' = {
  name: take('avm.res.appconfiguration.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    sku: sku
    disableLocalAuth: disableLocalAuth
    enablePurgeProtection: enablePurgeProtection
    softDeleteRetentionInDays: softDeleteRetentionInDays
    managedIdentities: managedIdentities
    roleAssignments: !empty(roleAssignments) ? roleAssignments : []
    keyValues: !empty(keyValues) ? keyValues : []
    publicNetworkAccess: !empty(publicNetworkAccess) ? publicNetworkAccess : null
    privateEndpoints: privateEndpoints
    diagnosticSettings: diagnosticSettings
    replicaLocations: replicaLocations
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('The name of the configuration store.')
output name string = configStore.outputs.name

@description('The endpoint of the configuration store.')
output endpoint string = configStore.outputs.endpoint

@description('The resource ID of the configuration store.')
output resourceId string = configStore.outputs.resourceId
