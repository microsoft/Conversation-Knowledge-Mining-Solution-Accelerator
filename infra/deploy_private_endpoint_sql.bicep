param solutionName string
param solutionLocation string
param sqlServerName string
param vnetId string 
param subnetId string 

resource sqlDns 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.database.windows.net'
  location: 'global'
}

resource sqlDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  name: '${solutionName}-sql-dns-link'
  parent: sqlDns
    location: 'global'
  properties: {
    virtualNetwork: {
      id: vnetId
    }
    registrationEnabled: false
  }
}
// Private Endpoint for SQL Server
resource sqlPrivateEndpoint 'Microsoft.Network/privateEndpoints@2021-05-01' = {
  name: '${solutionName}-sql-pe'
  location: solutionLocation
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [{
      name: '${solutionName}-sql-pls'
      properties: {
        privateLinkServiceId: resourceId('Microsoft.Sql/servers', sqlServerName)
        groupIds: ['sqlServer']
      }
    }]
  }
  dependsOn: [sqlDnsLink]
}

// Private DNS Zone Group for SQL Server
resource sqlPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2020-06-01' = {
  name: '${solutionName}-sql-dnszonegroup'
  parent: sqlPrivateEndpoint
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'sqlDnsConfig'
        properties: {
          privateDnsZoneId: sqlDns.id
        }
      }
    ]
  }
}
