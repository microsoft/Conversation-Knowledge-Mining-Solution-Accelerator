param solutionName string
param solutionLocation string
param keyVaultName string
param vnetId string 
param subnetId string 

resource keyVaultDns 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
}

resource keyVaultDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  name: '${solutionName}-kv-dns-link'
  parent: keyVaultDns
    location: 'global'
  properties: {
    virtualNetwork: {
      id: vnetId
    }
    registrationEnabled: false
  }
}

// Private Endpoint for Key Vault
resource keyVaultPrivateEndpoint 'Microsoft.Network/privateEndpoints@2021-05-01' = {
  name: '${solutionName}-kv-pe'
  location: solutionLocation
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [{
      name: '${solutionName}-kv-pls'
      properties: {
        privateLinkServiceId: resourceId('Microsoft.KeyVault/vaults', keyVaultName)
        groupIds: ['vault']
      }
    }]
  }
  dependsOn: [keyVaultDnsLink]
}

// Private DNS Zone Group for Key Vault
resource keyVaultPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2020-06-01' = {
  name: '${solutionName}-kv-dnszonegroup'
  parent: keyVaultPrivateEndpoint
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'keyVaultDnsConfig'
        properties: {
          privateDnsZoneId: keyVaultDns.id
        }
      }
    ]
  }
}
