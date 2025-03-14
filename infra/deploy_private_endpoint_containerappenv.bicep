param solutionName string
param solutionLocation string
param containerAppChartsName string
param containerAppRagName string
param vnetId string
param subnetId string 

// DNS Zone for Private Endpoints
resource containerAppDns 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.${solutionLocation}.azurecontainerapps.io'
  location: 'global'
}

// DNS Link for Private DNS Zone
resource containerAppDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  name: '${solutionName}-container-app-dns-link'
  parent: containerAppDns
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnetId
    }
    registrationEnabled: false
  }
}

// Private Endpoint for Container App Environment 1
resource containerAppChartsPrivateEndpoint 'Microsoft.Network/privateEndpoints@2021-05-01' = {
  name: '${solutionName}-containerappenvchart-pe'
  location: solutionLocation
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [ {
      name: '${solutionName}-containerappcharts-pls'
      properties: {
        privateLinkServiceId: resourceId('Microsoft.App/managedEnvironments', containerAppChartsName)
        groupIds: ['managedEnvironments']
      }
    } ]
  }
  dependsOn: [containerAppDnsLink]
}

// Private DNS Zone Group for Container App Environment 1
resource containerAppChartsPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2020-06-01' = {
  name: '${solutionName}-containerappenvcharts-dnszonegroup'
  parent: containerAppChartsPrivateEndpoint
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'containerAppChartsDnsConfig'
        properties: {
          privateDnsZoneId: containerAppDns.id
        }
      }
    ]
  }
}

// Private Endpoint for Container App Environment 2
resource containerAppRagPrivateEndpoint 'Microsoft.Network/privateEndpoints@2021-05-01' = {
  name: '${solutionName}-containerappenvrag-pe'
  location: solutionLocation
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [ {
      name: '${solutionName}-containerapprag-pls'
      properties: {
        privateLinkServiceId: resourceId('Microsoft.App/managedEnvironments', containerAppRagName)
        groupIds: ['managedEnvironments']
      }
    } ]
  }
  dependsOn: [containerAppDnsLink]
}

// Private DNS Zone Group for Container App Environment 2
resource containerAppRagPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2020-06-01' = {
  name: '${solutionName}-containerappenvrag-dnszonegroup'
  parent: containerAppRagPrivateEndpoint
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'containerAppRagDnsConfig'
        properties: {
          privateDnsZoneId: containerAppDns.id
        }
      }
    ]
  }
}

