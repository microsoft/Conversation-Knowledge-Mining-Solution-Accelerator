@description('Name of the Container App')
param name string

@description('Location for the resource')
param location string = resourceGroup().location

@description('Tags for the resource')
param tags object = {}

@description('Resource ID of the Container Apps Environment')
param containerAppsEnvironmentId string

@description('Target port the container listens on')
param targetPort int

@description('Environment variables for the container')
param env array = []

@description('Container image to deploy (leave empty for azd source-based deploy)')
param containerImage string = ''

@description('Minimum number of replicas')
param minReplicas int = 0

@description('Maximum number of replicas')
param maxReplicas int = 1

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'main'
          image: !empty(containerImage) ? containerImage : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          env: env
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

@description('The FQDN of the Container App')
output fqdn string = containerApp.properties.configuration.ingress.fqdn

@description('The URI of the Container App')
output uri string = 'https://${containerApp.properties.configuration.ingress.fqdn}'

@description('The principal ID of the system-assigned managed identity')
output principalId string = containerApp.identity.principalId

@description('The name of the Container App')
output name string = containerApp.name
