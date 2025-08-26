// ========== main.bicep ========== //
targetScope = 'resourceGroup'
//var abbrs = loadJsonContent('./abbreviations.json')
@minLength(3)
@maxLength(16)
@description('Required. A unique prefix for all resources in this deployment. This should be 3-20 characters long:')
param solutionName string = 'kmgen'

@description('Optional: Existing Log Analytics Workspace Resource ID')
param existingLogAnalyticsWorkspaceId string = ''

@description('Optional. Use this parameter to use an existing AI project resource ID')
param azureExistingAIProjectResourceId string = ''

@minLength(1)
@description('Optional. Location for the Content Understanding service deployment:')
@allowed(['swedencentral', 'australiaeast'])
@metadata({
  azd: {
    type: 'location'
  }
})
param contentUnderstandingLocation string = 'swedencentral'

@minLength(1)
@description('Optional. Secondary location for databases creation(example:eastus2):')
param secondaryLocation string = 'eastus2'

@minLength(1)
@description('Optional. GPT model deployment type:')
@allowed([
  'Standard'
  'GlobalStandard'
])
param deploymentType string = 'GlobalStandard'

@description('Optional. Name of the GPT model to deploy:')
param gptModelName string = 'gpt-4o-mini'

@description('Optional. Version of the GPT model to deploy:')
param gptModelVersion string = '2024-07-18'

@description('Optional. Version of the OpenAI.')
param azureOpenAIApiVersion string = '2025-01-01-preview'

@description('Optional. Version of AI Agent API.')
param azureAiAgentApiVersion string = '2025-05-01'

@minValue(10)
@description('Optional. Capacity of the GPT deployment:')
// You can increase this, but capacity is limited per model/region, so you will get errors if you go over
// https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits
param gptDeploymentCapacity int = 150

@minLength(1)
@description('Optional. Name of the Text Embedding model to deploy:')
@allowed([
  'text-embedding-ada-002'
])
param embeddingModel string = 'text-embedding-ada-002'

@minValue(10)
@description('Optional. Capacity of the Embedding Model deployment.')
param embeddingDeploymentCapacity int = 80

@description('Optional. Image Tag.')
param imageTag string = 'dev'

@description('Optional. Azure Location.')
param AZURE_LOCATION string = ''
var solutionLocation = empty(AZURE_LOCATION) ? resourceGroup().location : AZURE_LOCATION

//var uniqueId = toLower(uniqueString(subscription().id, solutionName, solutionLocation, resourceGroup().name))

@metadata({
  azd: {
    type: 'location'
    usageName: [
      'OpenAI.GlobalStandard.gpt-4o-mini,150'
      'OpenAI.GlobalStandard.text-embedding-ada-002,80'
    ]
  }
})
@description('Required. Location for AI Foundry deployment. This is the location where the AI Foundry resources will be deployed.')
param aiDeploymentsLocation string

//var solutionSuffix = 'km${padLeft(take(uniqueId, 12), 12, '0')}'

var acrName = 'kmcontainerreg'

var baseUrl = 'https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/psl-wafstandardization/'

@description('Optional. The tags to apply to all deployed Azure resources.')
param tags resourceInput<'Microsoft.Resources/resourceGroups@2025-04-01'>.tags = {}

@maxLength(5)
@description('Optional. A unique text value for the solution. This is used to ensure resource names are unique for global resources. Defaults to a 5-character substring of the unique string generated from the subscription ID, resource group name, and solution name.')
param solutionUniqueText string = substring(uniqueString(subscription().id, resourceGroup().name, solutionName), 0, 5)

var solutionSuffix = toLower(trim(replace(
  replace(
    replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''),
    ' ',
    ''
  ),
  '*',
  ''
)))
@description('Optional. Enable private networking for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enablePrivateNetworking bool = false
@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true
@description('Optional. Enable monitoring applicable resources, aligned with the Well Architected Framework recommendations. This setting enables Application Insights and Log Analytics and configures all the resources applicable resources to send logs. Defaults to false.')
param enableMonitoring bool = false
@description('Optional. Enable redundancy for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enableRedundancy bool = false
@description('Optional. Enable scalability for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enableScalability bool = false
@description('Optional. Enable purge protection for the Key Vault')
param enablePurgeProtection bool = false

@description('Optional. Admin username for the Jumpbox Virtual Machine. Set to custom value if enablePrivateNetworking is true.')
@secure()
param vmAdminUsername string?

@description('Optional. Admin password for the Jumpbox Virtual Machine. Set to custom value if enablePrivateNetworking is true.')
@secure()
param vmAdminPassword string?

@description('Optional. Size of the Jumpbox Virtual Machine when created. Set to custom value if enablePrivateNetworking is true.')
param vmSize string = 'Standard_DS2_v2'

// @description('Optional. Key vault reference and secret settings for the module\'s secrets export.')
// param secretsExportConfiguration secretsExportConfigurationType?
// Replica regions list based on article in [Azure regions list](https://learn.microsoft.com/azure/reliability/regions-list) and [Enhance resilience by replicating your Log Analytics workspace across regions](https://learn.microsoft.com/azure/azure-monitor/logs/workspace-replication#supported-regions) for supported regions for Log Analytics Workspace.
var replicaRegionPairs = {
  australiaeast: 'australiasoutheast'
  centralus: 'westus'
  eastasia: 'japaneast'
  eastus: 'centralus'
  eastus2: 'centralus'
  japaneast: 'eastasia'
  northeurope: 'westeurope'
  southeastasia: 'eastasia'
  uksouth: 'westeurope'
  westeurope: 'northeurope'
}
var replicaLocation = replicaRegionPairs[resourceGroup().location]
// Region pairs list based on article in [Azure Database for MySQL Flexible Server - Azure Regions](https://learn.microsoft.com/azure/mysql/flexible-server/overview#azure-regions) for supported high availability regions for CosmosDB.
var cosmosDbZoneRedundantHaRegionPairs = {
  australiaeast: 'uksouth' //'southeastasia'
  centralus: 'eastus2'
  eastasia: 'southeastasia'
  eastus: 'centralus'
  eastus2: 'centralus'
  japaneast: 'australiaeast'
  northeurope: 'westeurope'
  southeastasia: 'eastasia'
  uksouth: 'westeurope'
  westeurope: 'northeurope'
}
// Paired location calculated based on 'location' parameter. This location will be used by applicable resources if `enableScalability` is set to `true`
var cosmosDbHaLocation = cosmosDbZoneRedundantHaRegionPairs[resourceGroup().location]

// Extracts subscription, resource group, and workspace name from the resource ID when using an existing Log Analytics workspace
var useExistingLogAnalytics = !empty(existingLogAnalyticsWorkspaceId)
var logAnalyticsWorkspaceResourceId = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspaceId
  : logAnalyticsWorkspace!.outputs.resourceId
// ========== Resource Group Tag ========== //
resource resourceGroupTags 'Microsoft.Resources/tags@2021-04-01' = {
  name: 'default'
  properties: {
    tags: {
      ...tags
      TemplateName: 'KM Generic'
    }
  }
}

// ========== Log Analytics Workspace ========== //
// WAF best practices for Log Analytics: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-log-analytics
// WAF PSRules for Log Analytics: https://azure.github.io/PSRule.Rules.Azure/en/rules/resource/#azure-monitor-logs
var logAnalyticsWorkspaceResourceName = 'log-${solutionSuffix}'
module logAnalyticsWorkspace 'br/public:avm/res/operational-insights/workspace:0.12.0' = if (enableMonitoring) {
  name: take('avm.res.operational-insights.workspace.${logAnalyticsWorkspaceResourceName}', 64)
  params: {
    name: logAnalyticsWorkspaceResourceName
    tags: tags
    location: solutionLocation
    enableTelemetry: enableTelemetry
    skuName: 'PerGB2018'
    dataRetention: 365
    features: { enableLogAccessUsingOnlyResourcePermissions: true }
    diagnosticSettings: [{ useThisWorkspace: true }]
    // WAF aligned configuration for Redundancy
    dailyQuotaGb: enableRedundancy ? 10 : null //WAF recommendation: 10 GB per day is a good starting point for most workloads
    replication: enableRedundancy
      ? {
          enabled: true
          location: replicaLocation
        }
      : null
    // WAF aligned configuration for Private Networking
    publicNetworkAccessForIngestion: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    publicNetworkAccessForQuery: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    dataSources: enablePrivateNetworking
      ? [
          {
            tags: tags
            eventLogName: 'Application'
            eventTypes: [
              {
                eventType: 'Error'
              }
              {
                eventType: 'Warning'
              }
              {
                eventType: 'Information'
              }
            ]
            kind: 'WindowsEvent'
            name: 'applicationEvent'
          }
          {
            counterName: '% Processor Time'
            instanceName: '*'
            intervalSeconds: 60
            kind: 'WindowsPerformanceCounter'
            name: 'windowsPerfCounter1'
            objectName: 'Processor'
          }
          {
            kind: 'IISLogs'
            name: 'sampleIISLog1'
            state: 'OnPremiseEnabled'
          }
        ]
      : null
  }
}

// ========== Application Insights ========== //
// WAF best practices for Application Insights: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/application-insights
// WAF PSRules for  Application Insights: https://azure.github.io/PSRule.Rules.Azure/en/rules/resource/#application-insights
var applicationInsightsResourceName = 'appi-${solutionSuffix}'
module applicationInsights 'br/public:avm/res/insights/component:0.6.0' = if (enableMonitoring) {
  name: take('avm.res.insights.component.${applicationInsightsResourceName}', 64)
  params: {
    name: applicationInsightsResourceName
    tags: tags
    location: solutionLocation
    enableTelemetry: enableTelemetry
    retentionInDays: 365
    kind: 'web'
    disableIpMasking: false
    flowType: 'Bluefield'
    // WAF aligned configuration for Monitoring
    workspaceResourceId: enableMonitoring ? logAnalyticsWorkspaceResourceId : ''
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
  }
}

module network 'modules/network.bicep' = if (enablePrivateNetworking) {
  name: take('network-${solutionSuffix}-deployment', 64)
  params: {
    resourcesName: solutionSuffix
    logAnalyticsWorkSpaceResourceId: logAnalyticsWorkspaceResourceId
    vmAdminUsername: vmAdminUsername ?? 'JumpboxAdminUser'
    vmAdminPassword: vmAdminPassword ?? 'JumpboxAdminP@ssw0rd1234!'
    vmSize: vmSize ?? 'Standard_DS2_v2' // Default VM size 
    location: solutionLocation
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// ========== Network Security Groups ========== //
// WAF best practices for virtual networks: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/virtual-network
// WAF recommendations for networking and connectivity: https://learn.microsoft.com/en-us/azure/well-architected/security/networking
// var networkSecurityGroupWebsiteResourceName = 'nsg-${solutionSuffix}-website'
// module networkSecurityGroupWebsite 'br/public:avm/res/network/network-security-group:0.5.1' = if (enablePrivateNetworking) {
//   name: take('avm.res.network.network-security-group.${networkSecurityGroupWebsiteResourceName}', 64)
//   params: {
//     name: networkSecurityGroupWebsiteResourceName
//     location: solutionLocation
//     tags: tags
//     enableTelemetry: enableTelemetry
//     diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }] : null
//     securityRules: [
//       {
//         name: 'deny-hop-outbound'
//         properties: {
//           access: 'Deny'
//           destinationAddressPrefix: '*'
//           destinationPortRanges: [
//             '22'
//             '3389'
//           ]
//           direction: 'Outbound'
//           priority: 200
//           protocol: 'Tcp'
//           sourceAddressPrefix: 'VirtualNetwork'
//           sourcePortRange: '*'
//         }
//       }
//     ]
//   }
// }
// var networkSecurityGroupBackendResourceName = 'nsg-${solutionSuffix}-backend'
// module networkSecurityGroupBackend 'br/public:avm/res/network/network-security-group:0.5.1' = if (enablePrivateNetworking) {
//   name: take('avm.res.network.network-security-group.${networkSecurityGroupBackendResourceName}', 64)
//   params: {
//     name: networkSecurityGroupBackendResourceName
//     location: solutionLocation
//     tags: tags
//     enableTelemetry: enableTelemetry
//     diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }] : null
//     securityRules: [
//       {
//         name: 'deny-hop-outbound'
//         properties: {
//           access: 'Deny'
//           destinationAddressPrefix: '*'
//           destinationPortRanges: [
//             '22'
//             '3389'
//           ]
//           direction: 'Outbound'
//           priority: 200
//           protocol: 'Tcp'
//           sourceAddressPrefix: 'VirtualNetwork'
//           sourcePortRange: '*'
//         }
//       }
//     ]
//   }
// }
// var networkSecurityGroupAdministrationResourceName = 'nsg-${solutionSuffix}-administration'
// module networkSecurityGroupAdministration 'br/public:avm/res/network/network-security-group:0.5.1' = if (enablePrivateNetworking) {
//   name: take('avm.res.network.network-security-group.${networkSecurityGroupAdministrationResourceName}', 64)
//   params: {
//     name: networkSecurityGroupAdministrationResourceName
//     location: solutionLocation
//     tags: tags
//     enableTelemetry: enableTelemetry
//     diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }] : null
//     securityRules: [
//       {
//         name: 'deny-hop-outbound'
//         properties: {
//           access: 'Deny'
//           destinationAddressPrefix: '*'
//           destinationPortRanges: [
//             '22'
//             '3389'
//           ]
//           direction: 'Outbound'
//           priority: 200
//           protocol: 'Tcp'
//           sourceAddressPrefix: 'VirtualNetwork'
//           sourcePortRange: '*'
//         }
//       }
//     ]
//   }
// }
// var networkSecurityGroupBastionResourceName = 'nsg-${solutionSuffix}-bastion'
// module networkSecurityGroupBastion 'br/public:avm/res/network/network-security-group:0.5.1' = if (enablePrivateNetworking) {
//   name: take('avm.res.network.network-security-group.${networkSecurityGroupBastionResourceName}', 64)
//   params: {
//     name: networkSecurityGroupBastionResourceName
//     location: solutionLocation
//     tags: tags
//     enableTelemetry: enableTelemetry
//     diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }] : null
//     securityRules: [
//       {
//         name: 'AllowHttpsInBound'
//         properties: {
//           protocol: 'Tcp'
//           sourcePortRange: '*'
//           sourceAddressPrefix: 'Internet'
//           destinationPortRange: '443'
//           destinationAddressPrefix: '*'
//           access: 'Allow'
//           priority: 100
//           direction: 'Inbound'
//         }
//       }
//       {
//         name: 'AllowGatewayManagerInBound'
//         properties: {
//           protocol: 'Tcp'
//           sourcePortRange: '*'
//           sourceAddressPrefix: 'GatewayManager'
//           destinationPortRange: '443'
//           destinationAddressPrefix: '*'
//           access: 'Allow'
//           priority: 110
//           direction: 'Inbound'
//         }
//       }
//       {
//         name: 'AllowLoadBalancerInBound'
//         properties: {
//           protocol: 'Tcp'
//           sourcePortRange: '*'
//           sourceAddressPrefix: 'AzureLoadBalancer'
//           destinationPortRange: '443'
//           destinationAddressPrefix: '*'
//           access: 'Allow'
//           priority: 120
//           direction: 'Inbound'
//         }
//       }
//       {
//         name: 'AllowBastionHostCommunicationInBound'
//         properties: {
//           protocol: '*'
//           sourcePortRange: '*'
//           sourceAddressPrefix: 'VirtualNetwork'
//           destinationPortRanges: [
//             '8080'
//             '5701'
//           ]
//           destinationAddressPrefix: 'VirtualNetwork'
//           access: 'Allow'
//           priority: 130
//           direction: 'Inbound'
//         }
//       }
//       {
//         name: 'DenyAllInBound'
//         properties: {
//           protocol: '*'
//           sourcePortRange: '*'
//           sourceAddressPrefix: '*'
//           destinationPortRange: '*'
//           destinationAddressPrefix: '*'
//           access: 'Deny'
//           priority: 1000
//           direction: 'Inbound'
//         }
//       }
//       {
//         name: 'AllowSshRdpOutBound'
//         properties: {
//           protocol: 'Tcp'
//           sourcePortRange: '*'
//           sourceAddressPrefix: '*'
//           destinationPortRanges: [
//             '22'
//             '3389'
//           ]
//           destinationAddressPrefix: 'VirtualNetwork'
//           access: 'Allow'
//           priority: 100
//           direction: 'Outbound'
//         }
//       }
//       {
//         name: 'AllowAzureCloudCommunicationOutBound'
//         properties: {
//           protocol: 'Tcp'
//           sourcePortRange: '*'
//           sourceAddressPrefix: '*'
//           destinationPortRange: '443'
//           destinationAddressPrefix: 'AzureCloud'
//           access: 'Allow'
//           priority: 110
//           direction: 'Outbound'
//         }
//       }
//       {
//         name: 'AllowBastionHostCommunicationOutBound'
//         properties: {
//           protocol: '*'
//           sourcePortRange: '*'
//           sourceAddressPrefix: 'VirtualNetwork'
//           destinationPortRanges: [
//             '8080'
//             '5701'
//           ]
//           destinationAddressPrefix: 'VirtualNetwork'
//           access: 'Allow'
//           priority: 120
//           direction: 'Outbound'
//         }
//       }
//       {
//         name: 'AllowGetSessionInformationOutBound'
//         properties: {
//           protocol: '*'
//           sourcePortRange: '*'
//           sourceAddressPrefix: '*'
//           destinationAddressPrefix: 'Internet'
//           destinationPortRanges: [
//             '80'
//             '443'
//           ]
//           access: 'Allow'
//           priority: 130
//           direction: 'Outbound'
//         }
//       }
//       {
//         name: 'DenyAllOutBound'
//         properties: {
//           protocol: '*'
//           sourcePortRange: '*'
//           destinationPortRange: '*'
//           sourceAddressPrefix: '*'
//           destinationAddressPrefix: '*'
//           access: 'Deny'
//           priority: 1000
//           direction: 'Outbound'
//         }
//       }
//     ]
//   }
// }
// var networkSecurityGroupContainersResourceName = 'nsg-${solutionSuffix}-containers'
// module networkSecurityGroupContainers 'br/public:avm/res/network/network-security-group:0.5.1' = if (enablePrivateNetworking) {
//   name: take('avm.res.network.network-security-group.${networkSecurityGroupContainersResourceName}', 64)
//   params: {
//     name: networkSecurityGroupContainersResourceName
//     location: solutionLocation
//     tags: tags
//     enableTelemetry: enableTelemetry
//     diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }] : null
//     securityRules: [
//       {
//         name: 'deny-hop-outbound'
//         properties: {
//           access: 'Deny'
//           destinationAddressPrefix: '*'
//           destinationPortRanges: [
//             '22'
//             '3389'
//           ]
//           direction: 'Outbound'
//           priority: 200
//           protocol: 'Tcp'
//           sourceAddressPrefix: 'VirtualNetwork'
//           sourcePortRange: '*'
//         }
//       }
//     ]
//   }
// }
// // ========== Virtual Network ========== //
// // WAF best practices for virtual networks: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/virtual-network
// // WAF recommendations for networking and connectivity: https://learn.microsoft.com/en-us/azure/well-architected/security/networking
// var virtualNetworkResourceName = 'vnet-${solutionSuffix}'
// module virtualNetwork 'br/public:avm/res/network/virtual-network:0.7.0' = if (enablePrivateNetworking) {
//   name: take('avm.res.network.virtual-network.${virtualNetworkResourceName}', 64)
//   params: {
//     name: virtualNetworkResourceName
//     location: solutionLocation
//     tags: tags
//     enableTelemetry: enableTelemetry
//     addressPrefixes: ['10.0.0.0/8']
//     subnets: [
//       {
//         name: 'backend'
//         addressPrefix: '10.0.0.0/27'
//         //defaultOutboundAccess: false TODO: check this configuration for a more restricted outbound access
//         networkSecurityGroupResourceId: networkSecurityGroupBackend!.outputs.resourceId
//       }
//       {
//         name: 'administration'
//         addressPrefix: '10.0.0.32/27'
//         networkSecurityGroupResourceId: networkSecurityGroupAdministration!.outputs.resourceId
//         //defaultOutboundAccess: false TODO: check this configuration for a more restricted outbound access
//         //natGatewayResourceId: natGateway.outputs.resourceId
//       }
//       {
//         // For Azure Bastion resources deployed on or after November 2, 2021, the minimum AzureBastionSubnet size is /26 or larger (/25, /24, etc.).
//         // https://learn.microsoft.com/en-us/azure/bastion/configuration-settings#subnet
//         name: 'AzureBastionSubnet' //This exact name is required for Azure Bastion
//         addressPrefix: '10.0.0.64/26'
//         networkSecurityGroupResourceId: networkSecurityGroupBastion!.outputs.resourceId
//       }
//       {
//         // If you use your own vnw, you need to provide a subnet that is dedicated exclusively to the Container App environment you deploy. This subnet isn't available to other services
//         // https://learn.microsoft.com/en-us/azure/container-apps/networking?tabs=workload-profiles-env%2Cazure-cli#custom-vnw-configuration
//         name: 'containers'
//         addressPrefix: '10.0.2.0/23' //subnet of size /23 is required for container app
//         delegation: 'Microsoft.App/environments'
//         networkSecurityGroupResourceId: networkSecurityGroupContainers!.outputs.resourceId
//         privateEndpointNetworkPolicies: 'Enabled'
//         privateLinkServiceNetworkPolicies: 'Enabled'
//       }
//       {
//         // If you use your own vnw, you need to provide a subnet that is dedicated exclusively to the App Environment you deploy. This subnet isn't available to other services
//         // https://learn.microsoft.com/en-us/azure/app-service/overview-vnet-integration#subnet-requirements
//         name: 'webserverfarm'
//         addressPrefix: '10.0.4.0/27' //When you're creating subnets in Azure portal as part of integrating with the virtual network, a minimum size of /27 is required
//         delegation: 'Microsoft.Web/serverfarms'
//         networkSecurityGroupResourceId: networkSecurityGroupWebsite!.outputs.resourceId
//         privateEndpointNetworkPolicies: 'Enabled'
//         privateLinkServiceNetworkPolicies: 'Enabled'
//       }
//     ]
//   }
// }
// ========== Private DNS Zones ========== //
var privateDnsZones = [
  'privatelink.cognitiveservices.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.services.ai.azure.com'
  'privatelink.contentunderstanding.ai.azure.com'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.queue.${environment().suffixes.storage}'
  'privatelink.file.${environment().suffixes.storage}'
  'privatelink.api.azureml.ms'
  'privatelink.notebooks.azure.net'
  'privatelink.mongo.cosmos.azure.com'
  'privatelink.azconfig.io'
  'privatelink.vaultcore.azure.net'
  'privatelink.azurecr.io'
  'privatelink${environment().suffixes.sqlServerHostname}'
  'privatelink.azurewebsites.net'
  'privatelink.search.windows.net'
]
// DNS Zone Index Constants
var dnsZoneIndex = {
  cognitiveServices: 0
  openAI: 1
  aiServices: 2
  contentUnderstanding: 3
  storageBlob: 4
  storageQueue: 5
  storageFile: 6
  aiFoundry: 7
  notebooks: 8
  cosmosDB: 9
  appConfig: 10
  keyVault: 11
  containerRegistry: 12
  sqlServer: 13
  appService: 14
  search: 15
}
@batchSize(5)
module avmPrivateDnsZones 'br/public:avm/res/network/private-dns-zone:0.7.1' = [
  for (zone, i) in privateDnsZones: if (enablePrivateNetworking) {
    name: 'dns-zone-${i}'
    params: {
      name: zone
      tags: tags
      enableTelemetry: enableTelemetry
      virtualNetworkLinks: [{ virtualNetworkResourceId: network.outputs.subnetPrivateEndpointsResourceId }]
    }
  }
]

// ========== Managed Identity ========== //
// module managedIdentityModule 'deploy_managed_identity.bicep' = {
//   name: 'deploy_managed_identity'
//   params: {
//     miName:'id-${solutionSuffix}'
//     solutionName: solutionSuffix
//     solutionLocation: solutionLocation
//     tags : tags
//   }
//   scope: resourceGroup(resourceGroup().name)
// }

// ========== AVM WAF ========== //
// ========== User Assigned Identity ========== //
// WAF best practices for identity and access management: https://learn.microsoft.com/en-us/azure/well-architected/security/identity-access
var userAssignedIdentityResourceName = 'id-${solutionSuffix}'
module userAssignedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: take('avm.res.managed-identity.user-assigned-identity.${userAssignedIdentityResourceName}', 64)
  params: {
    name: userAssignedIdentityResourceName
    location: solutionLocation
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// ==========Key Vault Module ========== //
// module kvault 'deploy_keyvault.bicep' = {
//   name: 'deploy_keyvault'
//   params: {
//     keyvaultName: 'kv-${solutionSuffix}'
//     solutionLocation: solutionLocation
//     managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.objectId
//     tags : tags
//   }
//   scope: resourceGroup(resourceGroup().name)
// }

// ========== AVM WAF ========== //
// ========== Key Vault Module ========== //
var keyVaultName = 'KV-${solutionSuffix}'
module keyvault 'br/public:avm/res/key-vault/vault:0.12.1' = {
  name: take('avm.res.key-vault.vault.${keyVaultName}', 64)
  params: {
    name: keyVaultName
    location: solutionLocation
    tags: tags
    sku: 'premium'
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
    enablePurgeProtection: enablePurgeProtection
    enableVaultForDeployment: true
    enableVaultForDiskEncryption: true
    enableVaultForTemplateDeployment: true
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }] : []
    // WAF aligned configuration for Private Networking
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${keyVaultName}'
            customNetworkInterfaceName: 'nic-${keyVaultName}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                { privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.keyVault]!.outputs.resourceId }
              ]
            }
            service: 'vault'
            subnetResourceId: network.outputs.subnetPrivateEndpointsResourceId
          }
        ]
      : []
    // WAF aligned configuration for Role-based Access Control
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'Key Vault Administrator'
      }
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: '4633458b-17de-408a-b874-0445c86b69e6' // Key Vault Secrets User
      }
    ]
    // secrets: [
    //   {
    //     name: 'ExampleSecret'
    //     value: 'YourSecretValue'
    //   }
    // ]
    enableTelemetry: enableTelemetry
  }
}

// ==========AI Foundry and related resources ========== //
// ========== AI Foundry: AI Services ========== //
// WAF best practices for Open AI: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-openai

@description('Optional. Resource ID of an existing Foundry project')
param existingFoundryProjectResourceId string = ''
var existingOpenAIEndpoint = !empty(azureExistingAIProjectResourceId) ? format('https://{0}.openai.azure.com/', split(azureExistingAIProjectResourceId, '/')[8]) : ''
var existingProjEndpoint = !empty(azureExistingAIProjectResourceId) ? format('https://{0}.services.ai.azure.com/api/projects/{1}', split(azureExistingAIProjectResourceId, '/')[8], split(azureExistingAIProjectResourceId, '/')[10]) : ''
var existingAIServicesName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[8] : ''
var existingAIProjectName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[10] : ''
var existingAIServiceSubscription = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[2] : subscription().subscriptionId
var existingAIServiceResourceGroup = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[4] : resourceGroup().name

// NOTE: Required version 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' not available in AVM
var aiFoundryAiServicesResourceName = 'aif-${solutionSuffix}'
var aiFoundryAiServicesAiProjectResourceName = 'proj-${solutionSuffix}'
var aiFoundryAIservicesEnabled = true
var aiModelDeployments = [
  {
    name: gptModelName
    format: 'OpenAI'
    model: gptModelName
    sku: {
      name: deploymentType
      capacity: gptDeploymentCapacity
    }
    version: gptModelVersion
    raiPolicyName: 'Microsoft.Default'
  }
  {
    name: embeddingModel
    format: 'OpenAI'
    model: embeddingModel
    sku: {
      name: 'GlobalStandard'
      capacity: embeddingDeploymentCapacity
    }
    version: '2'
    raiPolicyName: 'Microsoft.Default'
  }
]

//TODO: update to AVM module when AI Projects and AI Projects RBAC are supported
module aiFoundryAiServices 'modules/ai-services.bicep' = if (aiFoundryAIservicesEnabled) {
  name: take('avm.res.cognitive-services.account.${aiFoundryAiServicesResourceName}', 64)
  params: {
    name: aiFoundryAiServicesResourceName
    location: aiDeploymentsLocation
    tags: tags
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    projectName: !empty(existingAIProjectName) ? existingAIProjectName : aiFoundryAiServicesAiProjectResourceName
    projectDescription: 'AI Foundry Project'
    sku: 'S0'
    kind: 'AIServices'
    disableLocalAuth: true
    customSubDomainName: aiFoundryAiServicesResourceName
    apiProperties: {
      //staticsEnabled: false
    }
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    managedIdentities: { userAssignedResourceIds: [userAssignedIdentity!.outputs.resourceId] } //To create accounts or projects, you must enable a managed identity on your resource
    roleAssignments: [
      {
        roleDefinitionIdOrName: '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Azure AI User
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: '64702f94-c441-49e6-a78b-ef80e0188fee' // Azure AI Developer
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
    ]
    // WAF aligned configuration for Monitoring
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    privateEndpoints: (enablePrivateNetworking &&  empty(existingFoundryProjectResourceId))
      ? ([
          {
            name: 'pep-${aiFoundryAiServicesResourceName}'
            customNetworkInterfaceName: 'nic-${aiFoundryAiServicesResourceName}'
            subnetResourceId: network.outputs.subnetPrivateEndpointsResourceId
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'ai-services-dns-zone-cognitiveservices'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
                }
                {
                  name: 'ai-services-dns-zone-openai'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.openAI]!.outputs.resourceId
                }
                {
                  name: 'ai-services-dns-zone-aiservices'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.aiServices]!.outputs.resourceId
                }
              ]
            }
          }
        ])
      : []
    deployments: [
      {
        name: aiModelDeployments[0].name
        model: {
          format: aiModelDeployments[0].format
          name: aiModelDeployments[0].name
          version: aiModelDeployments[0].version
        }
        raiPolicyName: aiModelDeployments[0].raiPolicyName
        sku: {
          name: aiModelDeployments[0].sku.name
          capacity: aiModelDeployments[0].sku.capacity
        }
      }
      {
        name: aiModelDeployments[1].name
        model: {
          format: aiModelDeployments[1].format
          name: aiModelDeployments[1].name
          version: aiModelDeployments[1].version
        }
        raiPolicyName: aiModelDeployments[1].raiPolicyName
        sku: {
          name: aiModelDeployments[1].sku.name
          capacity: aiModelDeployments[1].sku.capacity
        }
      }
    ]
  }
}

// AI Foundry: AI Services Content Understanding
var aiFoundryAiServicesCUResourceName = 'aif-${solutionSuffix}-cu'
var aiServicesName_cu = 'aisa-${solutionSuffix}-cu'
var varKvSecretNameAzureOpenaiCuKey = 'AZURE-OPENAI-CU-KEY'
// NOTE: Required version 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' not available in AVM
module avmCognitiveServicesAccountsContentUnderstanding 'br/public:avm/res/cognitive-services/account:0.10.1' = {
  name: take('avm.res.cognitive-services.account.${aiFoundryAiServicesCUResourceName}', 64)
  params: {
    name: aiServicesName_cu
    location: aiDeploymentsLocation
    tags: tags
    enableTelemetry: enableTelemetry
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    sku: 'S0'
    kind: 'AIServices'
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    managedIdentities: { userAssignedResourceIds: [userAssignedIdentity!.outputs.resourceId] } //To create accounts or projects, you must enable a managed identity on your resource
    disableLocalAuth: false //Added this in order to retrieve the keys. Evaluate alternatives
    customSubDomainName: aiServicesName_cu
    apiProperties: {
      // staticsEnabled: false
    }
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    privateEndpoints: (enablePrivateNetworking &&  empty(existingFoundryProjectResourceId))
      ? ([
          {
            name: 'pep-${aiFoundryAiServicesResourceName}'
            customNetworkInterfaceName: 'nic-${aiFoundryAiServicesResourceName}'
            subnetResourceId: network.outputs.subnetPrivateEndpointsResourceId
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'ai-services-dns-zone-cognitiveservices'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
                }
                {
                  name: 'ai-services-dns-zone-openai'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.openAI]!.outputs.resourceId
                }
                {
                  name: 'ai-services-dns-zone-aiservices'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.aiServices]!.outputs.resourceId
                }
              ]
            }
          }
        ])
      : []
    roleAssignments: [
      {
        roleDefinitionIdOrName: '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Azure AI User
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      //Options to add more roles if needed in the future
      // {
      //   roleDefinitionIdOrName: '64702f94-c441-49e6-a78b-ef80e0188fee' // Azure AI Developer
      //   principalId: userAssignedIdentity.outputs.principalId
      //   principalType: 'ServicePrincipal'
      // }
      // {
      //   roleDefinitionIdOrName: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User
      //   principalId: userAssignedIdentity.outputs.principalId
      //   principalType: 'ServicePrincipal'
      // }
    ]
    secretsExportConfiguration: {
      keyVaultResourceId: keyvault.outputs.resourceId
      accessKey1Name: varKvSecretNameAzureOpenaiCuKey
    }
  }
}

// If the above secretsExportConfiguration code not works to store the keys in key vault, uncomment below
// module saveAIServiceCUSecretsInKeyVault 'br/public:avm/res/key-vault/vault:0.12.1' = {
//   name: take('saveAIServiceCUSecretsInKeyVault.${keyVaultName}', 64)
//   params: {
//     name: keyVaultName
//     enablePurgeProtection: enablePurgeProtection
//     enableVaultForDeployment: true
//     enableVaultForDiskEncryption: true
//     enableVaultForTemplateDeployment: true
//     enableRbacAuthorization: true
//     enableSoftDelete: true
//     softDeleteRetentionInDays: 7
//     secrets: [
//       {
//         name: 'AZURE-OPENAI-CU-ENDPOINT'
//         value: avmCognitiveServicesAccountsContentUnderstanding.outputs.endpoints['OpenAI Language Model Instance API']
//       }
//     ]
//   }
// }

// ========== AI Foundry: AI Search ========== //
var aiSearchName = 'srch-${solutionName}'
var aiSearchConnectionName = 'myCon-${solutionName}'
var varKvSecretNameAzureSearchKey = 'AZURE-SEARCH-KEY'
// AI Foundry: AI Search
module avmSearchSearchServices 'br/public:avm/res/search/search-service:0.9.1' = {
  name: take('avm.res.cognitive-search-services.${aiSearchName}', 64)
  params: {
    name: aiSearchName
    tags: tags
    location: aiDeploymentsLocation
    enableTelemetry: enableTelemetry
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    sku: 'standard3'
    managedIdentities: { userAssignedResourceIds: [userAssignedIdentity!.outputs.resourceId] }
    replicaCount: 1
    partitionCount: 1
    // networkRuleSet: {
    //   ipRules: []
    // }
    roleAssignments: [
      {
        roleDefinitionIdOrName: 'Cognitive Services Contributor' // Cognitive Search Contributor
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'Cognitive Services OpenAI User'//'5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'// Cognitive Services OpenAI User
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
    ]
    disableLocalAuth: false
    // authOptions: {
    //   apiKeyOnly: {}
    // }
    semanticSearch: 'free'
    secretsExportConfiguration: {
      keyVaultResourceId: keyvault.outputs.resourceId
      primaryAdminKeyName: varKvSecretNameAzureSearchKey
    }
    // WAF aligned configuration for Private Networking
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${aiSearchName}'
            customNetworkInterfaceName: 'nic-${aiSearchName}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                { privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.search]!.outputs.resourceId }
              ]
            }
            subnetResourceId: network.outputs.subnetPrivateEndpointsResourceId
          }
        ]
      : []
  }
}
module existing_AIProject_SearchConnectionModule 'deploy_aifp_aisearch_connection.bicep' = if (!empty(azureExistingAIProjectResourceId)) {
  name: 'aiProjectSearchConnectionDeployment'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    existingAIProjectName: existingAIProjectName
    existingAIServicesName: existingAIServicesName
    aiSearchName: aiSearchName
    aiSearchResourceId: avmSearchSearchServices.outputs.resourceId
    aiSearchLocation: avmSearchSearchServices.outputs.location
    aiSearchConnectionName: aiSearchConnectionName
  }
}

// If the above secretsExportConfiguration code not works to store the keys in key vault, uncomment below
module saveAISearchServiceSecretsInKeyVault 'br/public:avm/res/key-vault/vault:0.12.1' = {
  name: take('saveAISearchServiceSecretsInKeyVault.${keyVaultName}', 64)
  params: {
    name: keyVaultName
    enablePurgeProtection: enablePurgeProtection
    enableVaultForDeployment: true
    enableVaultForDiskEncryption: true
    enableVaultForTemplateDeployment: true
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    secrets: [
      {
        name: 'AZURE-SEARCH-ENDPOINT'
        value: 'https://${avmSearchSearchServices.outputs.name}.search.windows.net'
      }
      {
        name: 'AZURE-SEARCH-SERVICE'
        value: avmSearchSearchServices.outputs.name
      }
      {
        name: 'AZURE-OPENAI-ENDPOINT'
        value: !empty(existingOpenAIEndpoint) ? existingOpenAIEndpoint : aiFoundryAiServices.outputs.endpoint
      }
      {
        name: 'COG-SERVICES-ENDPOINT'
        value: !empty(existingOpenAIEndpoint) ? existingOpenAIEndpoint : aiFoundryAiServices.outputs.endpoint
      }
      {
        name: 'AZURE-OPENAI-SEARCH-PROJECT'
        value: !empty(azureExistingAIProjectResourceId) ? existingAIProjectName : aiFoundryAiServicesAiProjectResourceName
      }
    ]
  }
}


// module aifoundry 'deploy_ai_foundry.bicep' = {
//   name: 'deploy_ai_foundry'
//   params: {
//     solutionName: solutionSuffix
//     solutionLocation: aiDeploymentsLocation
//     keyVaultName: keyvault.outputs.name
//     cuLocation: contentUnderstandingLocation
//     deploymentType: deploymentType
//     gptModelName: gptModelName
//     gptModelVersion: gptModelVersion
//     azureOpenAIApiVersion: azureOpenAIApiVersion
//     gptDeploymentCapacity: gptDeploymentCapacity
//     embeddingModel: embeddingModel
//     embeddingDeploymentCapacity: embeddingDeploymentCapacity
//     managedIdentityObjectId: userAssignedIdentity.outputs.principalId
//     existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
//     azureExistingAIProjectResourceId: azureExistingAIProjectResourceId
//     tags: tags
//   }
//   scope: resourceGroup(resourceGroup().name)
// }

// ========== Storage account module ========== //
// module storageAccount 'deploy_storage_account.bicep' = {
//   name: 'deploy_storage_account'
//   params: {
//     saName: 'st${solutionSuffix}'
//     solutionLocation: solutionLocation
//     keyVaultName: kvault.outputs.keyvaultName
//     managedIdentityObjectId: managedIdentityModule.outputs.managedIdentityOutput.objectId
//     tags : tags
//   }
//   scope: resourceGroup(resourceGroup().name)
// }

// ========== AVM WAF ========== //
// ========== Storage account module ========== //
var storageAccountName = 'st${solutionSuffix}'
module avmStorageAccount 'br/public:avm/res/storage/storage-account:0.20.0' = {
  name: take('avm.res.storage.storage-account.${storageAccountName}', 64)
  params: {
    name: storageAccountName
    location: solutionLocation
    managedIdentities: { systemAssigned: true }
    minimumTlsVersion: 'TLS1_2'
    enableTelemetry: enableTelemetry
    tags: tags
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        roleDefinitionIdOrName: 'Storage Blob Data Contributor'
        principalType: 'ServicePrincipal'
      }
    ]
    // WAF aligned networking
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: enablePrivateNetworking ? 'Deny' : 'Allow'
    }
    allowBlobPublicAccess: enablePrivateNetworking ? true : false
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    // Private endpoints for blob and queue
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-blob-${solutionSuffix}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'storage-dns-zone-group-blob'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageBlob]!.outputs.resourceId
                }
              ]
            }
            subnetResourceId: network.outputs.subnetPrivateEndpointsResourceId
            service: 'blob'
          }
          {
            name: 'pep-queue-${solutionSuffix}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'storage-dns-zone-group-queue'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageQueue]!.outputs.resourceId
                }
              ]
            }
            subnetResourceId: network.outputs.subnetPrivateEndpointsResourceId
            service: 'queue'
          }
        ]
      : []
    blobServices: {
      corsRules: []
      deleteRetentionPolicyEnabled: false
      containers: [
        {
          name: 'data'
          publicAccess: 'None'
        }
      ]
    }
    //   secretsExportConfiguration: {
    //   accessKey1Name: 'ADLS-ACCOUNT-NAME'
    //   connectionString1Name: storageAccountName
    //   accessKey2Name: 'ADLS-ACCOUNT-CONTAINER'
    //   connectionString2Name: 'data'
    //   accessKey3Name: 'ADLS-ACCOUNT-KEY'
    //   connectionString3Name: listKeys(resourceId('Microsoft.Storage/storageAccounts', storageAccountName), '2021-04-01')
    //   keyVaultResourceId: keyvault.outputs.resourceId
    // }
  }
  dependsOn: [keyvault]
  scope: resourceGroup(resourceGroup().name)
}

// working version of saving storage account secrets in key vault using AVM module
module saveStorageAccountSecretsInKeyVault 'br/public:avm/res/key-vault/vault:0.12.1' = {
  name: take('saveStorageAccountSecretsInKeyVault.${keyVaultName}', 64)
  params: {
    name: keyVaultName
    enablePurgeProtection: enablePurgeProtection
    enableVaultForDeployment: true
    enableVaultForDiskEncryption: true
    enableVaultForTemplateDeployment: true
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    secrets: [
      {
        name: 'ADLS-ACCOUNT-NAME'
        value: storageAccountName
      }
      {
        name: 'ADLS-ACCOUNT-CONTAINER'
        value: 'data'
      }
      {
        name: 'ADLS-ACCOUNT-KEY'
        value: avmStorageAccount.outputs.primaryAccessKey
      }
    ]
  }
}

// ========== Cosmos DB module ========== //
// module cosmosDBModule 'deploy_cosmos_db.bicep' = {
//   name: 'deploy_cosmos_db'
//   params: {
//     accountName: 'cosmos-${solutionSuffix}'
//     solutionLocation: secondaryLocation
//     keyVaultName: kvault.outputs.keyvaultName
//     tags : tags
//   }
//   scope: resourceGroup(resourceGroup().name)
// }

//========== AVM WAF ========== //
//========== Cosmos DB module ========== //
var cosmosDbResourceName = 'cosmos-${solutionSuffix}'
var cosmosDbDatabaseName = 'db_conversation_history'
// var cosmosDbDatabaseMemoryContainerName = 'memory'
var collectionName = 'conversations'
//TODO: update to latest version of AVM module
module cosmosDb 'br/public:avm/res/document-db/database-account:0.15.0' = {
  name: take('avm.res.document-db.database-account.${cosmosDbResourceName}', 64)
  params: {
    // Required parameters
    name: cosmosDbResourceName
    location: solutionLocation
    tags: tags
    enableTelemetry: enableTelemetry
    sqlDatabases: [
      {
        name: cosmosDbDatabaseName
        containers: [
          // {
          //   name: cosmosDbDatabaseMemoryContainerName
          //   paths: [
          //     '/session_id'
          //   ]
          //   kind: 'Hash'
          //   version: 2
          // }
          {
            name: collectionName
            paths: [
              '/userId'
            ]
          }
        ]
      }
    ]
    dataPlaneRoleDefinitions: [
      {
        // Cosmos DB Built-in Data Contributor: https://docs.azure.cn/en-us/cosmos-db/nosql/security/reference-data-plane-roles#cosmos-db-built-in-data-contributor
        roleName: 'Cosmos DB SQL Data Contributor'
        dataActions: [
          'Microsoft.DocumentDB/databaseAccounts/readMetadata'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/*'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*'
        ]
        assignments: [{ principalId: userAssignedIdentity.outputs.principalId }]
      }
    ]
    // WAF aligned configuration for Monitoring
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }] : null
    // WAF aligned configuration for Private Networking
    networkRestrictions: {
      networkAclBypass: 'None'
      publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    }
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${cosmosDbResourceName}'
            customNetworkInterfaceName: 'nic-${cosmosDbResourceName}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                { privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.cosmosDB]!.outputs.resourceId }
              ]
            }
            service: 'Sql'
            subnetResourceId: network.outputs.subnetPrivateEndpointsResourceId
          }
        ]
      : []
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'Contributor'
      }
    ]
    // WAF aligned configuration for Redundancy
    zoneRedundant: enableRedundancy ? true : false
    capabilitiesToAdd: enableRedundancy ? null : ['EnableServerless']
    automaticFailover: enableRedundancy ? true : false
    failoverLocations: enableRedundancy
      ? [
          {
            failoverPriority: 0
            isZoneRedundant: true
            locationName: solutionLocation
          }
          {
            failoverPriority: 1
            isZoneRedundant: true
            locationName: cosmosDbHaLocation
          }
        ]
      : [
          {
            locationName: solutionLocation
            failoverPriority: 0
          }
        ]
  }
  dependsOn: [keyvault, avmStorageAccount]
  scope: resourceGroup(resourceGroup().name)
}

// working version of saving Cosmos DB secrets in key vault using AVM module
module saveCosmosDBSecretsInKeyVault 'br/public:avm/res/key-vault/vault:0.12.1' = {
  name: take('saveCosmosDBSecretsInKeyVault.${keyVaultName}', 64)
  params: {
    name: keyVaultName
    enablePurgeProtection: enablePurgeProtection
    enableVaultForDeployment: true
    enableVaultForDiskEncryption: true
    enableVaultForTemplateDeployment: true
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    secrets: [
      {
        name: 'AZURE-COSMOSDB-ACCOUNT'
        value: cosmosDb.outputs.name
      }
      {
        name: 'AZURE-COSMOSDB-ACCOUNT-KEY'
        value: cosmosDb.outputs.primaryReadWriteKey
      }
      {
        name: 'AZURE-COSMOSDB-DATABASE'
        value: cosmosDbDatabaseName
      }
      {
        name: 'AZURE-COSMOSDB-CONVERSATIONS-CONTAINER'
        value: collectionName
      }
      {
        name: 'AZURE-COSMOSDB-ENABLE-FEEDBACK'
        value: 'True'
      }
    ]
  }
}

//========== SQL DB module ========== //
// module sqlDBModule 'deploy_sql_db.bicep' = {
//   name: 'deploy_sql_db'
//   params: {
//     serverName: 'sql-${solutionSuffix}'
//     sqlDBName: 'sqldb-${solutionSuffix}'
//     solutionLocation: secondaryLocation
//     keyVaultName: keyvault.outputs.name
//     managedIdentityName: userAssignedIdentity.outputs.name
//     sqlUsers: [
//       {
//         principalId: userAssignedIdentity.outputs.principalId
//         principalName: userAssignedIdentity.outputs.name
//         databaseRoles: ['db_datareader', 'db_datawriter']
//       }
//     ]
//     tags : tags
//   }
//   scope: resourceGroup(resourceGroup().name)
// }

module sqlDBModule 'br/public:avm/res/sql/server:0.20.1' = {
  name: 'serverDeployment'
  params: {
    // Required parameters
    name: 'sql-${solutionSuffix}'
    // Non-required parameters
    administrators: {
      azureADOnlyAuthentication: true
      login: userAssignedIdentity.outputs.name
      principalType: 'Application'
      sid: userAssignedIdentity.outputs.principalId
      tenantId: subscription().tenantId
    }
    connectionPolicy: 'Redirect'
    // customerManagedKey: {
    //   autoRotationEnabled: true
    //   keyName: keyvault.outputs.name
    //   keyVaultResourceId: keyvault.outputs.resourceId
    //   // keyVersion: keyvault.outputs.
    // }
    databases: [
      {
        availabilityZone: 1
        backupLongTermRetentionPolicy: {
          monthlyRetention: 'P6M'
        }
        backupShortTermRetentionPolicy: {
          retentionDays: 14
        }
        collation: 'SQL_Latin1_General_CP1_CI_AS'
        diagnosticSettings: enableMonitoring
          ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }]
          : null
        elasticPoolResourceId: resourceId(
          'Microsoft.Sql/servers/elasticPools',
          'sql-${solutionSuffix}',
          'sqlswaf-ep-001'
        )
        licenseType: 'LicenseIncluded'
        maxSizeBytes: 34359738368
        name: 'sqldb-${solutionSuffix}'
        sku: {
          capacity: 0
          name: 'ElasticPool'
          tier: 'GeneralPurpose'
        }
      }
    ]
    elasticPools: [
      {
        availabilityZone: -1
        //maintenanceConfigurationId: '<maintenanceConfigurationId>'
        name: 'sqlswaf-ep-001'
        sku: {
          capacity: 10
          name: 'GP_Gen5'
          tier: 'GeneralPurpose'
        }
        roleAssignments: [
          {
            principalId: userAssignedIdentity.outputs.principalId
            principalType: 'ServicePrincipal'
            roleDefinitionIdOrName: 'db_datareader'
          }
          {
            principalId: userAssignedIdentity.outputs.principalId
            principalType: 'ServicePrincipal'
            roleDefinitionIdOrName: 'db_datawriter'
          }

          //Enable if above access is not sufficient for your use case
          // {
          //   principalId: userAssignedIdentity.outputs.principalId
          //   principalType: 'ServicePrincipal'
          //   roleDefinitionIdOrName: 'SQL DB Contributor'
          // }
          // {
          //   principalId: userAssignedIdentity.outputs.principalId
          //   principalType: 'ServicePrincipal'
          //   roleDefinitionIdOrName: 'SQL Server Contributor'
          // }
        ]
      }
    ]
    firewallRules: [
      {
        endIpAddress: '255.255.255.255'
        name: 'AllowSpecificRange'
        startIpAddress: '0.0.0.0'
      }
      {
        endIpAddress: '0.0.0.0'
        name: 'AllowAllWindowsAzureIps'
        startIpAddress: '0.0.0.0'
      }
    ]
    location: solutionLocation
    managedIdentities: {
      systemAssigned: true
      userAssignedResourceIds: [
        userAssignedIdentity.outputs.resourceId
      ]
    }
    primaryUserAssignedIdentityResourceId: userAssignedIdentity.outputs.resourceId
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.sqlServer]!.outputs.resourceId
                }
              ]
            }
            service: 'sqlServer'
            subnetResourceId: network.outputs.subnetPrivateEndpointsResourceId
            tags: tags
          }
        ]
      : []
    restrictOutboundNetworkAccess: 'Disabled'
    securityAlertPolicies: [
      {
        emailAccountAdmins: true
        name: 'Default'
        state: 'Enabled'
      }
    ]
    tags: tags
    virtualNetworkRules: enablePrivateNetworking
      ? [
          {
            ignoreMissingVnetServiceEndpoint: true
            name: 'newVnetRule1'
            virtualNetworkSubnetResourceId: network.outputs.subnetPrivateEndpointsResourceId
          }
        ]
      : []
    vulnerabilityAssessmentsObj: {
      name: 'default'
      // recurringScans: {
      //   emails: [
      //     'test1@contoso.com'
      //     'test2@contoso.com'
      //   ]
      //   emailSubscriptionAdmins: true
      //   isEnabled: true
      // }
      storageAccountResourceId: avmStorageAccount.outputs.resourceId
    }
  }
}

//========== Deployment script to upload sample data ========== //
// module uploadFiles 'deploy_upload_files_script.bicep' = {
//   name : 'deploy_upload_files_script'
//   params:{
//     solutionLocation: secondaryLocation
//     baseUrl: baseUrl
//     storageAccountName: avmStorageAccount.outputs.name
//     containerName: 'data'
//     managedIdentityResourceId: userAssignedIdentity.outputs.resourceId
//     managedIdentityClientId: userAssignedIdentity.outputs.clientId
//   }
// }

// module createSqlUserAndRole 'br/public:avm/res/resources/deployment-script:0.5.1' = {
//   name: 'createSqlUserAndRoleScriptDeployment'
//   params: {
//     // Required parameters
//     kind: 'AzurePowerShell'
//     name: 'rdswaf001'
//     // Non-required parameters
//     azCliVersion: '2.52.0'
//     cleanupPreference: 'Always'
//     location: solutionLocation
//     lock: {
//       kind: 'None'
//     }
//     managedIdentities: {
//       userAssignedResourceIds: [
//         userAssignedIdentity.outputs.resourceId
//       ]
//     }
//     retentionInterval: 'P1D'
//     runOnce: true
//     primaryScriptUri: '${baseUrl}infra/scripts/copy_kb_files.sh'
//     arguments: join(
//       [
//         '-SqlServerName \'${ sqlDBModule.outputs.name }\''
//         '-SqlDatabaseName \'sqldb-${solutionSuffix}\''
//         '-ClientId \'${userAssignedIdentity.outputs.clientId}\''
//         '-DisplayName \'${userAssignedIdentity.outputs.name}\''
//         '-DatabaseRoles \'${join(databaseRoles, ',')}\''
//       ],
//       ' '
//     )
//     storageAccountResourceId: avmStorageAccount.outputs.resourceId
//     tags: tags
//     timeout: 'PT1H'
//   }
// }

//========== AVM WAF ========== //
//========== Deployment script to upload sample data ========== //
module uploadFiles 'br/public:avm/res/resources/deployment-script:0.5.1' = {
  name: 'deploymentScriptForUploadFiles'
  params: {
    // Required parameters
    kind: 'AzureCLI'
    name: 'copy_demo_Data'
    // Non-required parameters
    azCliVersion: '2.52.0'
    cleanupPreference: 'Always'
    location: secondaryLocation
    lock: {
      kind: 'None'
    }
    managedIdentities: {
      userAssignedResourceIds: [
        userAssignedIdentity.outputs.resourceId
      ]
    }
    retentionInterval: 'P1D'
    runOnce: true
    primaryScriptUri: '${baseUrl}infra/scripts/copy_kb_files.sh'
    arguments: '${storageAccountName} ${'data'} ${baseUrl} ${userAssignedIdentity.outputs.resourceId}'
    storageAccountResourceId: avmStorageAccount.outputs.resourceId
    tags: tags
    timeout: 'PT1H'
  }
}

//========== Deployment script to process and index data ========== //
// module createIndex 'deploy_index_scripts.bicep' = {
//   name : 'deploy_index_scripts'
//   params:{
//     solutionLocation: secondaryLocation
//     managedIdentityResourceId:userAssignedIdentity.outputs.resourceId
//     managedIdentityClientId:userAssignedIdentity.outputs.clientId
//     baseUrl:baseUrl
//     keyVaultName:aifoundry.outputs.keyvaultName
//     tags : tags
//   }
//   dependsOn:[sqlDBModule,uploadFiles]
// }

//========== AVM WAF ========== //
//========== Deployment script to create index ========== //
module createIndex 'br/public:avm/res/resources/deployment-script:0.5.1' = {
  name: 'deploymentScriptForCreateIndex'
  params: {
    // Required parameters
    kind: 'AzureCLI'
    name: 'create_search_indexes'
    // Non-required parameters
    azCliVersion: '2.52.0'
    cleanupPreference: 'Always'
    location: secondaryLocation
    lock: {
      kind: 'None'
    }
    managedIdentities: {
      userAssignedResourceIds: [
        userAssignedIdentity.outputs.resourceId
      ]
    }
    retentionInterval: 'P1D'
    runOnce: true
    primaryScriptUri: '${baseUrl}infra/scripts/run_create_index_scripts.sh'
    arguments: '${baseUrl} ${keyvault.outputs.name} ${userAssignedIdentity.outputs.clientId}'
    storageAccountResourceId: avmStorageAccount.outputs.resourceId
    tags: tags
    timeout: 'PT1H'
  }
  dependsOn: [sqlDBModule, uploadFiles]
}

// module hostingplan 'deploy_app_service_plan.bicep' = {
//   name: 'deploy_app_service_plan'
//   params: {
//     solutionLocation: solutionLocation
//     HostingPlanName: 'asp-${solutionSuffix}'
//     tags : tags
//   }
// }

// ========== AVM WAF server farm ========== //
// WAF best practices for Web Application Services: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/app-service-web-apps
// PSRule for Web Server Farm: https://azure.github.io/PSRule.Rules.Azure/en/rules/resource/#app-service
var webServerFarmResourceName = 'asp-${solutionSuffix}'
module webServerFarm 'br/public:avm/res/web/serverfarm:0.5.0' = {
  name: 'deploy_app_service_plan_serverfarm'
  params: {
    name: webServerFarmResourceName
    tags: tags
    enableTelemetry: enableTelemetry
    location: solutionLocation
    reserved: true
    kind: 'linux'
    // WAF aligned configuration for Monitoring
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }] : null
    // WAF aligned configuration for Scalability
    skuName: enableScalability || enableRedundancy ? 'P1v3' : 'B3'
    skuCapacity: enableScalability ? 3 : 1
    // WAF aligned configuration for Redundancy
    zoneRedundant: enableRedundancy ? true : false
  }
}

var reactAppLayoutConfig ='''{
  "appConfig": {
    "THREE_COLUMN": {
      "DASHBOARD": 50,
      "CHAT": 33,
      "CHATHISTORY": 17
    },
    "TWO_COLUMN": {
      "DASHBOARD_CHAT": {
        "DASHBOARD": 65,
        "CHAT": 35
      },
      "CHAT_CHATHISTORY": {
        "CHAT": 80,
        "CHATHISTORY": 20
      }
    }
  },
  "charts": [
    {
      "id": "SATISFIED",
      "name": "Satisfied",
      "type": "card",
      "layout": { "row": 1, "column": 1, "height": 11 }
    },
    {
      "id": "TOTAL_CALLS",
      "name": "Total Calls",
      "type": "card",
      "layout": { "row": 1, "column": 2, "span": 1 }
    },
    {
      "id": "AVG_HANDLING_TIME",
      "name": "Average Handling Time",
      "type": "card",
      "layout": { "row": 1, "column": 3, "span": 1 }
    },
    {
      "id": "SENTIMENT",
      "name": "Topics Overview",
      "type": "donutchart",
      "layout": { "row": 2, "column": 1, "width": 40, "height": 44.5 }
    },
    {
      "id": "AVG_HANDLING_TIME_BY_TOPIC",
      "name": "Average Handling Time By Topic",
      "type": "bar",
      "layout": { "row": 2, "column": 2, "row-span": 2, "width": 60 }
    },
    {
      "id": "TOPICS",
      "name": "Trending Topics",
      "type": "table",
      "layout": { "row": 3, "column": 1, "span": 2 }
    },
    {
      "id": "KEY_PHRASES",
      "name": "Key Phrases",
      "type": "wordcloud",
      "layout": { "row": 3, "column": 2, "height": 44.5 }
    }
  ]
}'''
var imageName = 'DOCKER|${acrName}.azurecr.io/km-api:${imageTag}'
var backendContainerRegistryHostname = '${acrName}.azurecr.io'
var backendWebSiteResourceName = 'api-${solutionSuffix}'
module avmBackend_Docker 'modules/web-sites.bicep' = {
  name: take('module.web-sites.${backendWebSiteResourceName}', 64)
  params: {
    name: backendWebSiteResourceName
    tags: tags
    location: solutionLocation
    kind: 'app,linux,container'
    serverFarmResourceId: webServerFarm.?outputs.resourceId
    managedIdentities: {
      systemAssigned: true
      userAssignedResourceIds: [
        userAssignedIdentity.outputs.resourceId
      ]
    }
    siteConfig: {
      linuxFxVersion: imageName
      minTlsVersion: '1.2'
    }
    configs: [
      {
        name: 'appsettings'
        properties: {
          SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
          DOCKER_REGISTRY_SERVER_URL: 'https://${backendContainerRegistryHostname}'
          WEBSITES_PORT: '8000'
          WEBSITES_CONTAINER_START_TIME_LIMIT: '1800' // 30 minutes, adjust as needed
          AUTH_ENABLED: 'false'
          REACT_APP_LAYOUT_CONFIG: reactAppLayoutConfig
          AZURE_OPENAI_DEPLOYMENT_MODEL: gptModelName
          AZURE_OPENAI_ENDPOINT: !empty(existingOpenAIEndpoint) ? existingOpenAIEndpoint : (aiFoundryAIservicesEnabled ? aiFoundryAiServices.outputs.endpoint : '')
          AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
          AZURE_OPENAI_RESOURCE: aiFoundryAIservicesEnabled ? aiFoundryAiServices.outputs.name : ''
          AZURE_AI_AGENT_ENDPOINT: !empty(existingProjEndpoint) ? existingProjEndpoint : (aiFoundryAIservicesEnabled ? aiFoundryAiServices.outputs.endpoint : '')
          AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
          AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
          USE_CHAT_HISTORY_ENABLED: 'True'
          AZURE_COSMOSDB_ACCOUNT: cosmosDb.outputs.name
          AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: collectionName
          AZURE_COSMOSDB_DATABASE: cosmosDbDatabaseName
          AZURE_COSMOSDB_ENABLE_FEEDBACK: 'True'
          SQLDB_DATABASE: 'sqldb-${solutionSuffix}'
          SQLDB_SERVER: '${sqlDBModule.outputs.name }${environment().suffixes.sqlServerHostname}'
          SQLDB_USER_MID: userAssignedIdentity.outputs.clientId
          AZURE_AI_SEARCH_ENDPOINT: 'https://${avmSearchSearchServices.outputs.name}.search.windows.net'
          AZURE_AI_SEARCH_INDEX: 'call_transcripts_index'
          AZURE_AI_SEARCH_CONNECTION_NAME: aiSearchConnectionName
          USE_AI_PROJECT_CLIENT: 'True'
          DISPLAY_CHART_DEFAULT: 'False'
          APPLICATIONINSIGHTS_CONNECTION_STRING: enableMonitoring ? applicationInsights!.outputs.connectionString : ''
          DUMMY_TEST: 'True'
          SOLUTION_NAME: solutionSuffix
          APP_ENV: 'Prod'
        }
        // WAF aligned configuration for Monitoring
        applicationInsightResourceId: enableMonitoring ? applicationInsights!.outputs.resourceId : null
      }
    ]
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    // WAF aligned configuration for Private Networking
    vnetRouteAllEnabled: enablePrivateNetworking ? true : false
    vnetImagePullEnabled: enablePrivateNetworking ? true : false
    virtualNetworkSubnetId: enablePrivateNetworking ? network!.outputs.subnetPrivateEndpointsResourceId : null
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${backendWebSiteResourceName}'
            customNetworkInterfaceName: 'nic-${backendWebSiteResourceName}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [{ privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.appService]!.outputs.resourceId }]
            }
            service: 'sites'
            subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
            roleAssignments: [
              {
                principalId: userAssignedIdentity.outputs.principalId
                principalType: 'ServicePrincipal'
                roleDefinitionIdOrName: 'Contributor'
              }
            ]
          }
        ]
      : null
  }
  scope: resourceGroup(resourceGroup().name)
}

// module cosmosDBRoleAssignmentForBackendAppService 'br/public:avm/res/document-db/database-account:0.15.0' = {
//   name: take('cosmosDBRoleAssignmentForBackendAppService-${cosmosDbResourceName}', 64)
//   params: {
//     // Required parameters
//     name: cosmosDbResourceName
//     roleAssignments: [
//       {
//         principalId: avmBackend_Docker.outputs.systemAssignedMIPrincipalId!
//         principalType: 'ServicePrincipal'
//         roleDefinitionIdOrName: 'Contributor'
//       }
//     ]
//   }
// }

// module keyVaultRoleAssignmentForBackendAppService 'br/public:avm/res/key-vault/vault:0.12.1' = {
//   name: take('keyVaultRoleAssignmentForBackendAppService.${keyVaultName}', 64)
//   params: {
//     name: keyVaultName
//     enablePurgeProtection: enablePurgeProtection
//     enableVaultForDeployment: true
//     enableVaultForDiskEncryption: true
//     enableVaultForTemplateDeployment: true
//     enableRbacAuthorization: true
//     enableSoftDelete: true
//     softDeleteRetentionInDays: 7
//     roleAssignments: [
//       {
//         principalId: avmBackend_Docker.outputs.systemAssignedMIPrincipalId!
//         principalType: 'ServicePrincipal'
//         roleDefinitionIdOrName: '4633458b-17de-408a-b874-0445c86b69e6'
//       }
//     ]
//   }
// }

// Yet to add aiFoundry role assignment for backend app service
// module aiFoundryRolesAssignmentToBackendAppService 'modules/ai-services.bicep' = if (aiFoundryAIservicesEnabled) {
//   name: take('aiFoundryRolesAssignmentToBackendAppService${aiFoundryAiServicesResourceName}', 64)
//   params: {
//     name: aiFoundryAiServicesResourceName
//     existingFoundryProjectResourceId: existingFoundryProjectResourceId
//     projectName: aiFoundryAiServicesAiProjectResourceName
//     projectDescription: 'AI Foundry Project'
//     sku: 'S0'
//     kind: 'AIServices'
//     roleAssignments: [
//       {
//         roleDefinitionIdOrName: '1407120a-92aa-4202-b7e9-c0e197c71c8f' // Search Index Data Reader
//         principalId: avmBackend_Docker.outputs.?systemAssignedMIPrincipalId
//         principalType: 'ServicePrincipal'
//       }
//     ]
//   }
// }


// module backend_docker 'deploy_backend_docker.bicep' = {
//   name: 'deploy_backend_docker'
//   params: {
//     name: 'api-${solutionSuffix}'
//     solutionLocation: solutionLocation
//     imageTag: imageTag
//     acrName: acrName
//     appServicePlanId: webServerFarm.outputs.name
//     applicationInsightsId: aifoundry.outputs.applicationInsightsId
//     userassignedIdentityId: userAssignedIdentity.outputs.principalId
//     keyVaultName: keyvault.outputs.name
//     aiServicesName: aifoundry.outputs.aiServicesName
//     azureExistingAIProjectResourceId: azureExistingAIProjectResourceId
//     aiSearchName: aifoundry.outputs.aiSearchName
//     appSettings: {
//       AZURE_OPENAI_DEPLOYMENT_MODEL: gptModelName
//       AZURE_OPENAI_ENDPOINT: aifoundry.outputs.aiServicesTarget
//       AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
//       AZURE_OPENAI_RESOURCE: aifoundry.outputs.aiServicesName
//       AZURE_AI_AGENT_ENDPOINT: aifoundry.outputs.projectEndpoint
//       AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
//       AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
//       USE_CHAT_HISTORY_ENABLED: 'True'
//       AZURE_COSMOSDB_ACCOUNT: cosmosDb.outputs.name
//       AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: collectionName
//       AZURE_COSMOSDB_DATABASE: cosmosDbDatabaseName
//       AZURE_COSMOSDB_ENABLE_FEEDBACK: 'True'
//       SQLDB_DATABASE: 'sqldb-${solutionSuffix}'
//       SQLDB_SERVER: '${sqlDBModule.outputs.name }${environment().suffixes.sqlServerHostname}'
//       SQLDB_USER_MID: userAssignedIdentity.outputs.clientId
//       AZURE_AI_SEARCH_ENDPOINT: aifoundry.outputs.aiSearchTarget
//       AZURE_AI_SEARCH_INDEX: 'call_transcripts_index'
//       AZURE_AI_SEARCH_CONNECTION_NAME: aifoundry.outputs.aiSearchConnectionName
//       USE_AI_PROJECT_CLIENT: 'True'
//       DISPLAY_CHART_DEFAULT: 'False'
//       APPLICATIONINSIGHTS_CONNECTION_STRING: aifoundry.outputs.applicationInsightsConnectionString
//       DUMMY_TEST: 'True'
//       SOLUTION_NAME: solutionSuffix
//       APP_ENV: 'Prod'
//     }
//     tags: tags
//   }
//   scope: resourceGroup(resourceGroup().name)
// }

@description('Optional. The Container Registry hostname where the docker images for the frontend are located.')
param frontendContainerRegistryHostname string = 'kmcontainerreg.azurecr.io'

@description('Optional. The Container Image Name to deploy on the frontend.')
param frontendContainerImageName string = 'km-app'

// @description('Optional. The Container Image Tag to deploy on the frontend.')
// param frontendContainerImageTag string = 'latest_2025-07-22_895'

// ========== Frontend web site ========== //
// WAF best practices for web app service: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/app-service-web-apps
// PSRule for Web Server Farm: https://azure.github.io/PSRule.Rules.Azure/en/rules/resource/#app-service

//NOTE: AVM module adds 1 MB of overhead to the template. Keeping vanilla resource to save template size.
var webSiteResourceName = 'app-${solutionSuffix}'
module avmFrontend_Docker 'modules/web-sites.bicep' = {
  name: take('module.web-sites.${webSiteResourceName}', 64)
  params: {
    name: webSiteResourceName
    tags: tags
    location: solutionLocation
    kind: 'app,linux,container'
    serverFarmResourceId: webServerFarm.?outputs.resourceId
    siteConfig: {
      linuxFxVersion: 'DOCKER|${frontendContainerRegistryHostname}/${frontendContainerImageName}:${imageTag}'
      minTlsVersion: '1.2'
    }
    configs: [
      {
        name: 'appsettings'
        properties: {
          SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
          DOCKER_REGISTRY_SERVER_URL: 'https://${frontendContainerRegistryHostname}'
          WEBSITES_PORT: '3000'
          WEBSITES_CONTAINER_START_TIME_LIMIT: '1800' // 30 minutes, adjust as needed
          BACKEND_API_URL: 'https://api-${solutionSuffix}.azurewebsites.net' //'https://${containerApp.outputs.fqdn}'
          AUTH_ENABLED: 'false'
        }
        // WAF aligned configuration for Monitoring
        applicationInsightResourceId: enableMonitoring ? applicationInsights!.outputs.resourceId : null
      }
    ]
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    // WAF aligned configuration for Private Networking
    vnetRouteAllEnabled: enablePrivateNetworking ? true : false
    vnetImagePullEnabled: enablePrivateNetworking ? true : false
    virtualNetworkSubnetId: enablePrivateNetworking ? network!.outputs.subnetPrivateEndpointsResourceId : null
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${webSiteResourceName}'
            customNetworkInterfaceName: 'nic-${webSiteResourceName}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                { privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.appService]!.outputs.resourceId }
              ]
            }
            service: 'sites'
            subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
          }
        ]
      : null
  }
  scope: resourceGroup(resourceGroup().name)
}

// var webSiteResourceName = 'app-${solutionSuffix}'
// module webSite 'modules/web-sites.bicep' = {
//   name: take('module.web-sites.${webSiteResourceName}', 64)
//   params: {
//     name: webSiteResourceName
//     tags: tags
//     location: solutionLocation
//     kind: 'app,linux,container'
//     serverFarmResourceId: webServerFarm.?outputs.resourceId
//     siteConfig: {
//       linuxFxVersion: 'DOCKER|${frontendContainerRegistryHostname}/${frontendContainerImageName}:${imageTag}'
//       minTlsVersion: '1.2'
//     }
//     configs: [
//       {
//         name: 'appsettings'
//         properties: {

//         }
//         // WAF aligned configuration for Monitoring
//         applicationInsightResourceId: enableMonitoring ? applicationInsights!.outputs.resourceId : null
//       }
//     ]
//     diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
//     // WAF aligned configuration for Private Networking
//     vnetRouteAllEnabled: enablePrivateNetworking ? true : false
//     vnetImagePullEnabled: enablePrivateNetworking ? true : false
//     virtualNetworkSubnetId: enablePrivateNetworking ? network!.outputs.subnetWebResourceId : null
//     publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
//     privateEndpoints: enablePrivateNetworking
//       ? [
//           {
//             name: 'pep-${webSiteResourceName}'
//             customNetworkInterfaceName: 'nic-${webSiteResourceName}'
//             privateDnsZoneGroup: {
//               privateDnsZoneGroupConfigs: [{ privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.appService]!.outputs.resourceId }]
//             }
//             service: 'sites'
//             subnetResourceId: network!.outputs.subnetWebResourceId
//           }
//         ]
//       : null
//   }
// }

// module frontend_docker 'deploy_frontend_docker.bicep' = {
//   name: 'deploy_frontend_docker'
//   params: {
//     name: 'app-${solutionSuffix}'
//     solutionLocation:solutionLocation
//     imageTag: imageTag
//     acrName: acrName
//     appServicePlanId: webServerFarm.outputs.resourceId
//     applicationInsightsId: aifoundry.outputs.applicationInsightsId
//     appSettings:{
//       APP_API_BASE_URL:backend_docker.outputs.appUrl
//     }
//     tags : tags
//   }
//   scope: resourceGroup(resourceGroup().name)
// }

@description('Contains Solution Name.')
output SOLUTION_NAME string = solutionSuffix

@description('Contains Resource Group Name.')
output RESOURCE_GROUP_NAME string = resourceGroup().name

@description('Contains Resource Group Location.')
output RESOURCE_GROUP_LOCATION string = solutionLocation

@description('Contains Azure Content Understanding Location.')
output AZURE_CONTENT_UNDERSTANDING_LOCATION string = contentUnderstandingLocation

@description('Contains Azure Secondary Location.')
output AZURE_SECONDARY_LOCATION string = secondaryLocation

@description('Contains Application Insights Instrumentation Key.')
output APPINSIGHTS_INSTRUMENTATIONKEY string = enableMonitoring ? applicationInsights!.outputs.instrumentationKey : ''

@description('Contains AI Project Connection String.')
output AZURE_AI_PROJECT_CONN_STRING string = !empty(existingProjEndpoint) ? existingProjEndpoint : aiFoundryAiServices.outputs.endpoint

@description('Contains Azure AI Agent API Version.')
output AZURE_AI_AGENT_API_VERSION string = azureAiAgentApiVersion

@description('Contains Azure AI Foundry service name.')
output AZURE_AI_FOUNDRY_NAME string = !empty(existingAIServicesName) ? existingAIServicesName : aiFoundryAiServices.outputs.name

@description('Contains Azure AI Project name.')
output AZURE_AI_PROJECT_NAME string = !empty(existingAIProjectName) ? existingAIProjectName : aiFoundryAiServices.outputs.aiProjectInfo.name

@description('Contains Azure AI Search service name.')
output AZURE_AI_SEARCH_NAME string = !empty(existingAIServicesName) ? existingAIServicesName : aiFoundryAiServicesResourceName

@description('Contains Azure AI Search endpoint URL.')
output AZURE_AI_SEARCH_ENDPOINT string = 'https://${aiFoundryAiServices.outputs.name}.search.windows.net'

@description('Contains Azure AI Search index name.')
output AZURE_AI_SEARCH_INDEX string = 'call_transcripts_index'

@description('Contains Azure AI Search connection name.')
output AZURE_AI_SEARCH_CONNECTION_NAME string = aiSearchConnectionName

@description('Contains Azure Cosmos DB account name.')
output AZURE_COSMOSDB_ACCOUNT string = cosmosDb.outputs.name

@description('Contains Azure Cosmos DB conversations container name.')
output AZURE_COSMOSDB_CONVERSATIONS_CONTAINER string = 'conversations'

@description('Contains Azure Cosmos DB database name.')
output AZURE_COSMOSDB_DATABASE string = 'db_conversation_history'

@description('Contains Azure Cosmos DB feedback enablement setting.')
output AZURE_COSMOSDB_ENABLE_FEEDBACK string = 'True'

@description('Contains Azure OpenAI deployment model name.')
output AZURE_OPENAI_DEPLOYMENT_MODEL string = gptModelName

@description('Contains Azure OpenAI deployment model capacity.')
output AZURE_OPENAI_DEPLOYMENT_MODEL_CAPACITY int = gptDeploymentCapacity

@description('Contains Azure OpenAI endpoint URL.')
output AZURE_OPENAI_ENDPOINT string = 'https://${aiFoundryAiServices.outputs.name}.search.windows.net'

@description('Contains Azure OpenAI model deployment type.')
output AZURE_OPENAI_MODEL_DEPLOYMENT_TYPE string = deploymentType

@description('Contains Azure OpenAI embedding model name.')
output AZURE_OPENAI_EMBEDDING_MODEL string = embeddingModel

@description('Contains Azure OpenAI embedding model capacity.')
output AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY int = embeddingDeploymentCapacity

@description('Contains Azure OpenAI API version.')
output AZURE_OPENAI_API_VERSION string = azureOpenAIApiVersion

@description('Contains Azure OpenAI resource name.')
output AZURE_OPENAI_RESOURCE string = aiFoundryAiServices.outputs.name

@description('Contains React app layout configuration.')
output REACT_APP_LAYOUT_CONFIG string = reactAppLayoutConfig

@description('Contains SQL database name.')
output SQLDB_DATABASE string = 'sqldb-${solutionSuffix}'

@description('Contains SQL server name.')
output SQLDB_SERVER string = sqlDBModule.outputs.name

@description('Contains SQL database user managed identity client ID.')
output SQLDB_USER_MID string = userAssignedIdentity.outputs.clientId

@description('Contains AI project client usage setting.')
output USE_AI_PROJECT_CLIENT string = 'False'

@description('Contains chat history enablement setting.')
output USE_CHAT_HISTORY_ENABLED string = 'True'

@description('Contains default chart display setting.')
output DISPLAY_CHART_DEFAULT string = 'False'

@description('Contains Azure AI Agent endpoint URL.')
output AZURE_AI_AGENT_ENDPOINT string = !empty(existingProjEndpoint) ? existingProjEndpoint : aiFoundryAiServices.outputs.endpoint

@description('Contains Azure AI Agent model deployment name.')
output AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME string = gptModelName

@description('Contains Azure Container Registry name.')
output ACR_NAME string = acrName

@description('Contains Azure environment image tag.')
output AZURE_ENV_IMAGETAG string = imageTag

@description('Contains existing AI project resource ID.')
output AZURE_EXISTING_AI_PROJECT_RESOURCE_ID string = azureExistingAIProjectResourceId

@description('Contains Application Insights connection string.')
output APPLICATIONINSIGHTS_CONNECTION_STRING string = enableMonitoring ? applicationInsights!.outputs.connectionString : ''

@description('Contains API application URL.')
output API_APP_URL string = 'https://app-${solutionName}.azurewebsites.net'

@description('Contains web application URL.')
output WEB_APP_URL string = 'https://api-${solutionName}.azurewebsites.net'
