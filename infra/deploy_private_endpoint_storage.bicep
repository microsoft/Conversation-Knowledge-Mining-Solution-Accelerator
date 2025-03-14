param solutionName string
param solutionLocation string
param storageAccountName string
param storageAccountHubName string
param vnetId string
param subnetId string

resource storageDns 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.blob.core.windows.net'
  location: 'global'
}

resource storageDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  name: '${solutionName}-storage-dns-link'
  parent: storageDns
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnetId
    }
    registrationEnabled: false
  }
}

// Private Endpoint for Storage Account
resource storagePrivateEndpoint 'Microsoft.Network/privateEndpoints@2021-05-01' = {
  name: '${solutionName}-storage-pe'
  location: solutionLocation
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [{
      name: '${solutionName}-storage-pls'
      properties: {
        privateLinkServiceId: resourceId('Microsoft.Storage/storageAccounts', storageAccountName)
        groupIds: ['blob']
      }
    }]
  }
  dependsOn: [storageDnsLink]
}

// Private DNS Zone Group for Storage Account
resource storagePrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2020-06-01' = {
  name: '${solutionName}-storage-dnszonegroup'
  parent: storagePrivateEndpoint
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'storageDnsConfig'
        properties: {
          privateDnsZoneId: storageDns.id
        }
      }
    ]
  }
}

resource storageHubPrivateEndpoint 'Microsoft.Network/privateEndpoints@2021-05-01' = {
  name: '${solutionName}-storagehub-pe'
  location: solutionLocation
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [{
      name: '${solutionName}-storagehub-pls'
      properties: {
        privateLinkServiceId: resourceId('Microsoft.Storage/storageAccounts', storageAccountHubName)
        groupIds: ['blob']
      }
    }]
  }
  dependsOn: [storageDnsLink]
}

// Private DNS Zone Group for Storage Account
resource storageHUbPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2020-06-01' = {
  name: '${solutionName}-storagehub-dnszonegroup'
  parent: storageHubPrivateEndpoint
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'storageHubDnsConfig'
        properties: {
          privateDnsZoneId: storageDns.id
        }
      }
    ]
  }
}

output storagePrivateDnsZoneId string = storageDns.id
