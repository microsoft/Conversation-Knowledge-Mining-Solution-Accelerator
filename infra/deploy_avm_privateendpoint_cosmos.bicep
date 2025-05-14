param solutionName string
param solutionLocation string
param vnetId string 
param subnetId string 
param cosmosDBAccountName string

module privateDnsZone 'br/public:avm/res/network/private-dns-zone:0.7.0' = {
  name: 'privateDnsZoneDeployment'
  params: {
    name: 'privatelink.documents.azure.com'
    location: 'global' 
    virtualNetworkLinks: [
      {
        registrationEnabled: true
        virtualNetworkResourceId: vnetId
      }
    ]
  }
}

module privateEndpoint 'br/public:avm/res/network/private-endpoint:0.10.1' = {
  name: 'privateEndpointDeployment'
  params: {
    name: '${solutionName}-cosmos-pe'
    subnetResourceId: subnetId
    location: solutionLocation
    privateDnsZoneGroup: {
      name: 'default'
      privateDnsZoneGroupConfigs: [
        {
          name: 'config'
          privateDnsZoneResourceId: privateDnsZone.outputs.resourceId
        }
      ]
    }
    privateLinkServiceConnections: [
      {
        name: '${solutionName}-cosmos-pls'
        properties: {
          groupIds: ['Sql']
          privateLinkServiceId:  resourceId('Microsoft.DocumentDB/databaseAccounts', cosmosDBAccountName)
        }
      }
    ]
    
  }
}

