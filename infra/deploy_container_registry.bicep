targetScope = 'resourceGroup'

@description('Required. Contains Solution Name.')
param environmentName string

@description('Required. Contains Solution Location.')
param solutionLocation string = resourceGroup().location

var uniqueId = toLower(uniqueString(subscription().id, environmentName, solutionLocation))
var solutionName = 'km${padLeft(take(uniqueId, 12), 12, '0')}'
//var abbrs = loadJsonContent('./abbreviations.json')
var containerRegistryName = 'cr${solutionName}'
var containerRegistryNameCleaned = replace(containerRegistryName, '-', '')
 
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2021-09-01' = {
  name: containerRegistryName
  location: solutionLocation
  sku: {
    name: 'Premium'
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
 
@description('Contains Created ACR Name.')
output createdAcrName string = containerRegistryNameCleaned

@description('Contains Created ACR ID')
output createdAcrId string = containerRegistry.id
 