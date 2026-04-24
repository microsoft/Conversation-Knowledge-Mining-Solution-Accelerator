@description('Name of the Container Apps Environment')
param name string

@description('Location for the resource')
param location string = resourceGroup().location

@description('Tags for the resource')
param tags object = {}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    zoneRedundant: false
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

@description('The resource ID of the Container Apps Environment')
output environmentId string = containerAppsEnvironment.id

@description('The name of the Container Apps Environment')
output name string = containerAppsEnvironment.name
