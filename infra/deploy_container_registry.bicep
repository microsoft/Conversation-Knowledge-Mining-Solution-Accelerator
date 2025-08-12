targetScope = 'resourceGroup'

param solutionName string
param solutionLocation string = resourceGroup().location

var abbrs = loadJsonContent('./abbreviations.json')
var containerRegistryName = '${abbrs.containers.containerRegistry}${solutionName}'
var containerRegistryNameCleaned = replace(containerRegistryName, '-', '')

@description('List of Principal Ids to which ACR pull role assignment is required')
param acrPullPrincipalIds array = []

@description('Provide a tier of your Azure Container Registry.')
param acrSku string = 'Premium'
 
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2021-09-01' = {
  name: containerRegistryName
  location: solutionLocation
  sku: {
    name: acrSku
  }
  properties: {
    dataEndpointEnabled: false
    networkRuleBypassOptions: 'AzureServices'
    networkRuleSet: {
      defaultAction: 'Allow'
    }
    policies: {
      quarantinePolicy: {
        status: 'disabled'
      }
      retentionPolicy: {
        status: 'enabled'
        days: 7
      }
      trustPolicy: {
        status: 'disabled'
        type: 'Notary'
      }
    }
    publicNetworkAccess: 'Enabled'
    zoneRedundancy: 'Disabled'
  }
}

// Add Role assignments for required principal id's
resource acrPullRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in acrPullPrincipalIds: {
  name: guid(principalId, 'acrpull')
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
    principalId: principalId
  }
}]
 
output createdAcrName string = containerRegistryNameCleaned
output createdAcrId string = containerRegistry.id
 