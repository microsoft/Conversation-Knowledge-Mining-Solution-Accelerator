param name string
param location string
param tags object

@description('SKU for the search service')
@allowed(['free', 'basic', 'standard', 'standard2', 'standard3'])
param skuName string = 'basic'

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: { name: skuName }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
  }
}

output endpoint string = 'https://${name}.search.windows.net'
output name string = search.name
output id string = search.id
