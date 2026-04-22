param name string
param location string
param tags object

resource contentUnderstanding 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  tags: tags
  kind: 'CognitiveServices'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
    apiProperties: {}
  }
}

output endpoint string = contentUnderstanding.properties.endpoint
output name string = contentUnderstanding.name
output id string = contentUnderstanding.id
