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
param AZURE_LOCATION string=''
var solutionLocation = empty(AZURE_LOCATION) ? resourceGroup().location : AZURE_LOCATION

//var uniqueId = toLower(uniqueString(subscription().id, solutionName, solutionLocation, resourceGroup().name))

@metadata({
  azd:{
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
@description('Optional. Enable purge protection for the Key Vault')
param enablePurgeProtection bool = false
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

// ========== Resource Group Tag ========== //
resource resourceGroupTags 'Microsoft.Resources/tags@2021-04-01' = {
  name: 'default'
  properties: {
    tags: {
      ... tags
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
// ========== Network Security Groups ========== //
// WAF best practices for virtual networks: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/virtual-network
// WAF recommendations for networking and connectivity: https://learn.microsoft.com/en-us/azure/well-architected/security/networking
var networkSecurityGroupWebsiteResourceName = 'nsg-${solutionSuffix}-website'
module networkSecurityGroupWebsite 'br/public:avm/res/network/network-security-group:0.5.1' = if (enablePrivateNetworking) {
  name: take('avm.res.network.network-security-group.${networkSecurityGroupWebsiteResourceName}', 64)
  params: {
    name: networkSecurityGroupWebsiteResourceName
    location: solutionLocation
    tags: tags
    enableTelemetry: enableTelemetry
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }] : null
    securityRules: [
      {
        name: 'deny-hop-outbound'
        properties: {
          access: 'Deny'
          destinationAddressPrefix: '*'
          destinationPortRanges: [
            '22'
            '3389'
          ]
          direction: 'Outbound'
          priority: 200
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
        }
      }
    ]
  }
}
var networkSecurityGroupBackendResourceName = 'nsg-${solutionSuffix}-backend'
module networkSecurityGroupBackend 'br/public:avm/res/network/network-security-group:0.5.1' = if (enablePrivateNetworking) {
  name: take('avm.res.network.network-security-group.${networkSecurityGroupBackendResourceName}', 64)
  params: {
    name: networkSecurityGroupBackendResourceName
    location: solutionLocation
    tags: tags
    enableTelemetry: enableTelemetry
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }] : null
    securityRules: [
      {
        name: 'deny-hop-outbound'
        properties: {
          access: 'Deny'
          destinationAddressPrefix: '*'
          destinationPortRanges: [
            '22'
            '3389'
          ]
          direction: 'Outbound'
          priority: 200
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
        }
      }
    ]
  }
}
var networkSecurityGroupAdministrationResourceName = 'nsg-${solutionSuffix}-administration'
module networkSecurityGroupAdministration 'br/public:avm/res/network/network-security-group:0.5.1' = if (enablePrivateNetworking) {
  name: take('avm.res.network.network-security-group.${networkSecurityGroupAdministrationResourceName}', 64)
  params: {
    name: networkSecurityGroupAdministrationResourceName
    location: solutionLocation
    tags: tags
    enableTelemetry: enableTelemetry
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }] : null
    securityRules: [
      {
        name: 'deny-hop-outbound'
        properties: {
          access: 'Deny'
          destinationAddressPrefix: '*'
          destinationPortRanges: [
            '22'
            '3389'
          ]
          direction: 'Outbound'
          priority: 200
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
        }
      }
    ]
  }
}
var networkSecurityGroupBastionResourceName = 'nsg-${solutionSuffix}-bastion'
module networkSecurityGroupBastion 'br/public:avm/res/network/network-security-group:0.5.1' = if (enablePrivateNetworking) {
  name: take('avm.res.network.network-security-group.${networkSecurityGroupBastionResourceName}', 64)
  params: {
    name: networkSecurityGroupBastionResourceName
    location: solutionLocation
    tags: tags
    enableTelemetry: enableTelemetry
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }] : null
    securityRules: [
      {
        name: 'AllowHttpsInBound'
        properties: {
          protocol: 'Tcp'
          sourcePortRange: '*'
          sourceAddressPrefix: 'Internet'
          destinationPortRange: '443'
          destinationAddressPrefix: '*'
          access: 'Allow'
          priority: 100
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowGatewayManagerInBound'
        properties: {
          protocol: 'Tcp'
          sourcePortRange: '*'
          sourceAddressPrefix: 'GatewayManager'
          destinationPortRange: '443'
          destinationAddressPrefix: '*'
          access: 'Allow'
          priority: 110
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowLoadBalancerInBound'
        properties: {
          protocol: 'Tcp'
          sourcePortRange: '*'
          sourceAddressPrefix: 'AzureLoadBalancer'
          destinationPortRange: '443'
          destinationAddressPrefix: '*'
          access: 'Allow'
          priority: 120
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowBastionHostCommunicationInBound'
        properties: {
          protocol: '*'
          sourcePortRange: '*'
          sourceAddressPrefix: 'VirtualNetwork'
          destinationPortRanges: [
            '8080'
            '5701'
          ]
          destinationAddressPrefix: 'VirtualNetwork'
          access: 'Allow'
          priority: 130
          direction: 'Inbound'
        }
      }
      {
        name: 'DenyAllInBound'
        properties: {
          protocol: '*'
          sourcePortRange: '*'
          sourceAddressPrefix: '*'
          destinationPortRange: '*'
          destinationAddressPrefix: '*'
          access: 'Deny'
          priority: 1000
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowSshRdpOutBound'
        properties: {
          protocol: 'Tcp'
          sourcePortRange: '*'
          sourceAddressPrefix: '*'
          destinationPortRanges: [
            '22'
            '3389'
          ]
          destinationAddressPrefix: 'VirtualNetwork'
          access: 'Allow'
          priority: 100
          direction: 'Outbound'
        }
      }
      {
        name: 'AllowAzureCloudCommunicationOutBound'
        properties: {
          protocol: 'Tcp'
          sourcePortRange: '*'
          sourceAddressPrefix: '*'
          destinationPortRange: '443'
          destinationAddressPrefix: 'AzureCloud'
          access: 'Allow'
          priority: 110
          direction: 'Outbound'
        }
      }
      {
        name: 'AllowBastionHostCommunicationOutBound'
        properties: {
          protocol: '*'
          sourcePortRange: '*'
          sourceAddressPrefix: 'VirtualNetwork'
          destinationPortRanges: [
            '8080'
            '5701'
          ]
          destinationAddressPrefix: 'VirtualNetwork'
          access: 'Allow'
          priority: 120
          direction: 'Outbound'
        }
      }
      {
        name: 'AllowGetSessionInformationOutBound'
        properties: {
          protocol: '*'
          sourcePortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: 'Internet'
          destinationPortRanges: [
            '80'
            '443'
          ]
          access: 'Allow'
          priority: 130
          direction: 'Outbound'
        }
      }
      {
        name: 'DenyAllOutBound'
        properties: {
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
          access: 'Deny'
          priority: 1000
          direction: 'Outbound'
        }
      }
    ]
  }
}
var networkSecurityGroupContainersResourceName = 'nsg-${solutionSuffix}-containers'
module networkSecurityGroupContainers 'br/public:avm/res/network/network-security-group:0.5.1' = if (enablePrivateNetworking) {
  name: take('avm.res.network.network-security-group.${networkSecurityGroupContainersResourceName}', 64)
  params: {
    name: networkSecurityGroupContainersResourceName
    location: solutionLocation
    tags: tags
    enableTelemetry: enableTelemetry
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId }] : null
    securityRules: [
      {
        name: 'deny-hop-outbound'
        properties: {
          access: 'Deny'
          destinationAddressPrefix: '*'
          destinationPortRanges: [
            '22'
            '3389'
          ]
          direction: 'Outbound'
          priority: 200
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
        }
      }
    ]
  }
}
// ========== Virtual Network ========== //
// WAF best practices for virtual networks: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/virtual-network
// WAF recommendations for networking and connectivity: https://learn.microsoft.com/en-us/azure/well-architected/security/networking
var virtualNetworkResourceName = 'vnet-${solutionSuffix}'
module virtualNetwork 'br/public:avm/res/network/virtual-network:0.7.0' = if (enablePrivateNetworking) {
  name: take('avm.res.network.virtual-network.${virtualNetworkResourceName}', 64)
  params: {
    name: virtualNetworkResourceName
    location: solutionLocation
    tags: tags
    enableTelemetry: enableTelemetry
    addressPrefixes: ['10.0.0.0/8']
    subnets: [
      {
        name: 'backend'
        addressPrefix: '10.0.0.0/27'
        //defaultOutboundAccess: false TODO: check this configuration for a more restricted outbound access
        networkSecurityGroupResourceId: networkSecurityGroupBackend!.outputs.resourceId
      }
      {
        name: 'administration'
        addressPrefix: '10.0.0.32/27'
        networkSecurityGroupResourceId: networkSecurityGroupAdministration!.outputs.resourceId
        //defaultOutboundAccess: false TODO: check this configuration for a more restricted outbound access
        //natGatewayResourceId: natGateway.outputs.resourceId
      }
      {
        // For Azure Bastion resources deployed on or after November 2, 2021, the minimum AzureBastionSubnet size is /26 or larger (/25, /24, etc.).
        // https://learn.microsoft.com/en-us/azure/bastion/configuration-settings#subnet
        name: 'AzureBastionSubnet' //This exact name is required for Azure Bastion
        addressPrefix: '10.0.0.64/26'
        networkSecurityGroupResourceId: networkSecurityGroupBastion!.outputs.resourceId
      }
      {
        // If you use your own vnw, you need to provide a subnet that is dedicated exclusively to the Container App environment you deploy. This subnet isn't available to other services
        // https://learn.microsoft.com/en-us/azure/container-apps/networking?tabs=workload-profiles-env%2Cazure-cli#custom-vnw-configuration
        name: 'containers'
        addressPrefix: '10.0.2.0/23' //subnet of size /23 is required for container app
        delegation: 'Microsoft.App/environments'
        networkSecurityGroupResourceId: networkSecurityGroupContainers!.outputs.resourceId
        privateEndpointNetworkPolicies: 'Enabled'
        privateLinkServiceNetworkPolicies: 'Enabled'
      }
      {
        // If you use your own vnw, you need to provide a subnet that is dedicated exclusively to the App Environment you deploy. This subnet isn't available to other services
        // https://learn.microsoft.com/en-us/azure/app-service/overview-vnet-integration#subnet-requirements
        name: 'webserverfarm'
        addressPrefix: '10.0.4.0/27' //When you're creating subnets in Azure portal as part of integrating with the virtual network, a minimum size of /27 is required
        delegation: 'Microsoft.Web/serverfarms'
        networkSecurityGroupResourceId: networkSecurityGroupWebsite!.outputs.resourceId
        privateEndpointNetworkPolicies: 'Enabled'
        privateLinkServiceNetworkPolicies: 'Enabled'
      }
    ]
  }
}
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
}
@batchSize(5)
module avmPrivateDnsZones 'br/public:avm/res/network/private-dns-zone:0.7.1' = [
  for (zone, i) in privateDnsZones: if (enablePrivateNetworking) {
    name: 'dns-zone-${i}'
    params: {
      name: zone
      tags: tags
      enableTelemetry: enableTelemetry
      virtualNetworkLinks: [{ virtualNetworkResourceId: virtualNetwork!.outputs.resourceId }]
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
            subnetResourceId: virtualNetwork!.outputs.subnetResourceIds[0]
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
module aifoundry 'deploy_ai_foundry.bicep' = {
  name: 'deploy_ai_foundry'
  params: {
    solutionName: solutionSuffix
    solutionLocation: aiDeploymentsLocation
    keyVaultName: keyvault.outputs.name
    cuLocation: contentUnderstandingLocation
    deploymentType: deploymentType
    gptModelName: gptModelName
    gptModelVersion: gptModelVersion
    azureOpenAIApiVersion: azureOpenAIApiVersion
    gptDeploymentCapacity: gptDeploymentCapacity
    embeddingModel: embeddingModel
    embeddingDeploymentCapacity: embeddingDeploymentCapacity
    managedIdentityObjectId: userAssignedIdentity.outputs.principalId
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
    azureExistingAIProjectResourceId: azureExistingAIProjectResourceId
    tags : tags

  }
  scope: resourceGroup(resourceGroup().name)
}


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
            subnetResourceId: virtualNetwork!.outputs.subnetResourceIds[0]
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
            subnetResourceId: virtualNetwork!.outputs.subnetResourceIds[0]
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
            subnetResourceId: virtualNetwork!.outputs.subnetResourceIds[0]
          }
        ]
      : []
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
module sqlDBModule 'deploy_sql_db.bicep' = {
  name: 'deploy_sql_db'
  params: {
    serverName: 'sql-${solutionSuffix}'
    sqlDBName: 'sqldb-${solutionSuffix}'
    solutionLocation: secondaryLocation
    keyVaultName: keyvault.outputs.name
    managedIdentityName: userAssignedIdentity.outputs.name
    sqlUsers: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalName: userAssignedIdentity.outputs.name
        databaseRoles: ['db_datareader', 'db_datawriter']
      }
    ]
    tags : tags
  }
  scope: resourceGroup(resourceGroup().name)
}

//========== Deployment script to upload sample data ========== //
module uploadFiles 'deploy_upload_files_script.bicep' = {
  name : 'deploy_upload_files_script'
  params:{
    solutionLocation: secondaryLocation
    baseUrl: baseUrl
    storageAccountName: avmStorageAccount.outputs.name
    containerName: 'data'
    managedIdentityResourceId: userAssignedIdentity.outputs.resourceId
    managedIdentityClientId: userAssignedIdentity.outputs.clientId
  }
}

//========== Deployment script to process and index data ========== //
module createIndex 'deploy_index_scripts.bicep' = {
  name : 'deploy_index_scripts'
  params:{
    solutionLocation: secondaryLocation
    managedIdentityResourceId:userAssignedIdentity.outputs.resourceId
    managedIdentityClientId:userAssignedIdentity.outputs.clientId
    baseUrl:baseUrl
    keyVaultName:aifoundry.outputs.keyvaultName
    tags : tags
  }
  dependsOn:[sqlDBModule,uploadFiles]
}

module hostingplan 'deploy_app_service_plan.bicep' = {
  name: 'deploy_app_service_plan'
  params: {
    solutionLocation: solutionLocation
    HostingPlanName: 'asp-${solutionSuffix}'
    tags : tags
  }
}

module backend_docker 'deploy_backend_docker.bicep' = {
  name: 'deploy_backend_docker'
  params: {
    name: 'api-${solutionSuffix}'
    solutionLocation: solutionLocation
    imageTag: imageTag
    acrName: acrName
    appServicePlanId: hostingplan.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    userassignedIdentityId: userAssignedIdentity.outputs.principalId
    keyVaultName: keyvault.outputs.name
    aiServicesName: aifoundry.outputs.aiServicesName
    azureExistingAIProjectResourceId: azureExistingAIProjectResourceId
    aiSearchName: aifoundry.outputs.aiSearchName
    appSettings: {
      AZURE_OPENAI_DEPLOYMENT_MODEL: gptModelName
      AZURE_OPENAI_ENDPOINT: aifoundry.outputs.aiServicesTarget
      AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
      AZURE_OPENAI_RESOURCE: aifoundry.outputs.aiServicesName
      AZURE_AI_AGENT_ENDPOINT: aifoundry.outputs.projectEndpoint
      AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
      AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
      USE_CHAT_HISTORY_ENABLED: 'True'
      AZURE_COSMOSDB_ACCOUNT: cosmosDb.outputs.name
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: collectionName
      AZURE_COSMOSDB_DATABASE: cosmosDbDatabaseName
      AZURE_COSMOSDB_ENABLE_FEEDBACK: 'True'
      SQLDB_DATABASE: 'sqldb-${solutionSuffix}'
      SQLDB_SERVER: '${sqlDBModule.outputs.sqlServerName}${environment().suffixes.sqlServerHostname}'
      SQLDB_USER_MID: userAssignedIdentity.outputs.clientId
      AZURE_AI_SEARCH_ENDPOINT: aifoundry.outputs.aiSearchTarget
      AZURE_AI_SEARCH_INDEX: 'call_transcripts_index'
      AZURE_AI_SEARCH_CONNECTION_NAME: aifoundry.outputs.aiSearchConnectionName
      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: aifoundry.outputs.applicationInsightsConnectionString
      DUMMY_TEST: 'True'
      SOLUTION_NAME: solutionSuffix
      APP_ENV: 'Prod'
    }
    tags: tags
  }
  scope: resourceGroup(resourceGroup().name)
}

module frontend_docker 'deploy_frontend_docker.bicep' = {
  name: 'deploy_frontend_docker'
  params: {
    name: 'app-${solutionSuffix}'
    solutionLocation:solutionLocation
    imageTag: imageTag
    acrName: acrName
    appServicePlanId: hostingplan.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    appSettings:{
      APP_API_BASE_URL:backend_docker.outputs.appUrl
    }
    tags : tags
  }
  scope: resourceGroup(resourceGroup().name)
}

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
output APPINSIGHTS_INSTRUMENTATIONKEY string = backend_docker.outputs.appInsightInstrumentationKey

@description('Contains AI Project Connection String.')
output AZURE_AI_PROJECT_CONN_STRING string = aifoundry.outputs.projectEndpoint


@description('Contains Azure AI Agent API Version.')
output AZURE_AI_AGENT_API_VERSION string = azureAiAgentApiVersion

@description('Contains Azure AI Foundry service name.')
output AZURE_AI_FOUNDRY_NAME string = aifoundry.outputs.aiServicesName

@description('Contains Azure AI Project name.')
output AZURE_AI_PROJECT_NAME string = aifoundry.outputs.aiProjectName

@description('Contains Azure AI Search service name.')
output AZURE_AI_SEARCH_NAME string = aifoundry.outputs.aiSearchName

@description('Contains Azure AI Search endpoint URL.')
output AZURE_AI_SEARCH_ENDPOINT string = aifoundry.outputs.aiSearchTarget

@description('Contains Azure AI Search index name.')
output AZURE_AI_SEARCH_INDEX string = 'call_transcripts_index'

@description('Contains Azure AI Search connection name.')
output AZURE_AI_SEARCH_CONNECTION_NAME string = aifoundry.outputs.aiSearchConnectionName

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
output AZURE_OPENAI_ENDPOINT string = aifoundry.outputs.aiServicesTarget

@description('Contains Azure OpenAI model deployment type.')
output AZURE_OPENAI_MODEL_DEPLOYMENT_TYPE string = deploymentType

@description('Contains Azure OpenAI embedding model name.')
output AZURE_OPENAI_EMBEDDING_MODEL string = embeddingModel

@description('Contains Azure OpenAI embedding model capacity.')
output AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY int = embeddingDeploymentCapacity

@description('Contains Azure OpenAI API version.')
output AZURE_OPENAI_API_VERSION string = azureOpenAIApiVersion

@description('Contains Azure OpenAI resource name.')
output AZURE_OPENAI_RESOURCE string = aifoundry.outputs.aiServicesName

@description('Contains React app layout configuration.')
output REACT_APP_LAYOUT_CONFIG string = backend_docker.outputs.reactAppLayoutConfig

@description('Contains SQL database name.')
output SQLDB_DATABASE string = sqlDBModule.outputs.sqlDbName

@description('Contains SQL server name.')
output SQLDB_SERVER string = sqlDBModule.outputs.sqlServerName

@description('Contains SQL database user managed identity client ID.')
output SQLDB_USER_MID string = userAssignedIdentity.outputs.clientId

@description('Contains AI project client usage setting.')
output USE_AI_PROJECT_CLIENT string = 'False'

@description('Contains chat history enablement setting.')
output USE_CHAT_HISTORY_ENABLED string = 'True'

@description('Contains default chart display setting.')
output DISPLAY_CHART_DEFAULT string = 'False'

@description('Contains Azure AI Agent endpoint URL.')
output AZURE_AI_AGENT_ENDPOINT string = aifoundry.outputs.projectEndpoint

@description('Contains Azure AI Agent model deployment name.')
output AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME string = gptModelName

@description('Contains Azure Container Registry name.')
output ACR_NAME string = acrName

@description('Contains Azure environment image tag.')
output AZURE_ENV_IMAGETAG string = imageTag

@description('Contains existing AI project resource ID.')
output AZURE_EXISTING_AI_PROJECT_RESOURCE_ID string = azureExistingAIProjectResourceId

@description('Contains Application Insights connection string.')
output APPLICATIONINSIGHTS_CONNECTION_STRING string = aifoundry.outputs.applicationInsightsConnectionString

@description('Contains API application URL.')
output API_APP_URL string = backend_docker.outputs.appUrl

@description('Contains web application URL.')
output WEB_APP_URL string = frontend_docker.outputs.appUrl
