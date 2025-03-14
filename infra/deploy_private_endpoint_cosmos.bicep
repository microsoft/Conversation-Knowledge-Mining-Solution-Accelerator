param solutionName string
param solutionLocation string
param cosmosDBAccountName string
param vnetId string 
param subnetId string 

resource cosmosDns 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.documents.azure.com'
  location: 'global'
}

resource cosmosDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  name: '${solutionName}-cosmos-dns-link'
  parent: cosmosDns
    location: 'global'
  properties: {
    virtualNetwork: {
      id: vnetId
    }
    registrationEnabled: false
  }
}

// Private Endpoint for Cosmos DB
resource cosmosPrivateEndpoint 'Microsoft.Network/privateEndpoints@2021-05-01' = {
  name: '${solutionName}-cosmos-pe'
  location: solutionLocation
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [{
      name: '${solutionName}-cosmos-pls'
      properties: {
        privateLinkServiceId: resourceId('Microsoft.DocumentDB/databaseAccounts', cosmosDBAccountName)
        groupIds: ['Sql']
      }
    }]
  }
  dependsOn: [cosmosDnsLink]
}

// Private DNS Zone Group for Cosmos DB
resource cosmosPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2020-06-01' = {
  name: '${solutionName}-cosmos-dnszonegroup'
  parent: cosmosPrivateEndpoint
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'cosmosDnsConfig'
        properties: {
          privateDnsZoneId: cosmosDns.id
        }
      }
    ]
  }
}
