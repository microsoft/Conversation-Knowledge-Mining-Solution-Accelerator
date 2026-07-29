metadata description = 'Creates a dedicated Azure Container Registry for the application container images.'

@description('Required. Name of the container registry (alphanumeric, 5-50 chars, globally unique).')
param name string

@description('Optional. Location for the registry.')
param location string = resourceGroup().location

@description('Optional. Tags for the registry.')
param tags object = {}

@description('Optional. SKU for the registry.')
@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param sku string = 'Standard'

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

@description('The name of the container registry.')
output name string = registry.name

@description('The login server of the container registry.')
output loginServer string = registry.properties.loginServer

@description('The resource ID of the container registry.')
output resourceId string = registry.id
