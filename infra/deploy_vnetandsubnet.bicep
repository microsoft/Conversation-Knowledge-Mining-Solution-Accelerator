@minLength(3)
@maxLength(15)
@description('Solution Name')
param solutionName string
param solutionLocation string

var vnetName = '${solutionName}-VNet'
var addressPrefixVnet = '10.0.0.0/16'
var subnet1Name = '${solutionName}-mainsubnet'
var subnet2Name = '${solutionName}-fncharts-subnet'
var subnet3Name = '${solutionName}-fnrag-subnet'
var subnet4Name = '${solutionName}-appservice-subnet'

var addressPrefixSubnet1 = '10.0.1.0/24'
var addressPrefixSubnet2 = '10.0.2.0/24'
var addressPrefixSubnet3 = '10.0.3.0/24'
var addressPrefixSubnet4 = '10.0.4.0/24'

// Create the Virtual Network (VNet)
resource vnet 'Microsoft.Network/virtualNetworks@2021-02-01' = {
  name: vnetName
  location: solutionLocation
  properties: {
    addressSpace: {
      addressPrefixes: [
        addressPrefixVnet
      ]
    }
  }
}

// Create Subnet 1
resource subnet1 'Microsoft.Network/virtualNetworks/subnets@2021-02-01' = {
  parent: vnet
  name: subnet1Name
  properties: {
    addressPrefix: addressPrefixSubnet1
  }
}

// Create Subnet 2
resource subnet2 'Microsoft.Network/virtualNetworks/subnets@2021-02-01' = {
  parent: vnet
  name: subnet2Name
  properties: {
    addressPrefix: addressPrefixSubnet2
    delegations: [
      {
        name: 'delegation'
        properties: {
          serviceName: 'Microsoft.App/environments'
        }
      }
    ]
  }
  dependsOn: [
    subnet1
  ]
}

// Create Subnet 3
resource subnet3 'Microsoft.Network/virtualNetworks/subnets@2021-02-01' = {
  parent: vnet
  name: subnet3Name
  properties: {
    addressPrefix: addressPrefixSubnet3
    delegations: [
      {
        name: 'delegation'
        properties: {
          serviceName: 'Microsoft.App/environments'
        }
      }
    ]
  }
  dependsOn: [
    subnet2
  ]
}

// Create Subnet 4
resource subnet4 'Microsoft.Network/virtualNetworks/subnets@2021-02-01' = {
  parent: vnet
  name: subnet4Name
  properties: {
    addressPrefix: addressPrefixSubnet4
  }
  dependsOn: [
    subnet3
  ]
}

output vnetId string = vnet.id
output subnet1Id string = subnet1.id
output subnet2Id string = subnet2.id
output subnet3Id string = subnet3.id
output subnet4Id string = subnet4.id
