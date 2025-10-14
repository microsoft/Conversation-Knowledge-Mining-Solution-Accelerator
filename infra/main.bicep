// ========== main.bicep ========== //
targetScope = 'resourceGroup'

@minLength(3)
@maxLength(16)
@description('Required. A unique prefix for all resources in this deployment. This should be 3-20 characters long:')
param solutionName string = 'kmgen'

@metadata({ azd: { type: 'location' } })
@description('Required. Azure region for all services. Regions are restricted to guarantee compatibility with paired regions and replica locations for data redundancy and failover scenarios based on articles [Azure regions list](https://learn.microsoft.com/azure/reliability/regions-list) and [Azure Database for MySQL Flexible Server - Azure Regions](https://learn.microsoft.com/azure/mysql/flexible-server/overview#azure-regions).')
@allowed([
  'australiaeast'
  'centralus'
  'eastasia'
  'eastus2'
  'japaneast'
  'northeurope'
  'southeastasia'
  'uksouth'
])
param location string

@allowed([
  'australiaeast'
  'eastus'
  'eastus2'
  'francecentral'
  'japaneast'
  'swedencentral'
  'uksouth'
  'westus'
  'westus3'
])
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
param aiServiceLocation string

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

// You can increase this, but capacity is limited per model/region, so you will get errors if you go over
// https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits
@minValue(10)
@description('Optional. Capacity of the GPT deployment:')
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

@description('Optional. The Container Registry hostname where the docker images for the backend are located.')
param backendContainerRegistryHostname string = 'kmcontainerreg.azurecr.io'

@description('Optional. The Container Image Name to deploy on the backend.')
param backendContainerImageName string = 'km-api'

@description('Optional. The Container Image Tag to deploy on the backend.')
param backendContainerImageTag string = 'latest_waf_2025-09-18_898'

@description('Optional. The Container Registry hostname where the docker images for the frontend are located.')
param frontendContainerRegistryHostname string = 'kmcontainerreg.azurecr.io'

@description('Optional. The Container Image Name to deploy on the frontend.')
param frontendContainerImageName string = 'km-app'

@description('Optional. The Container Image Tag to deploy on the frontend.')
param frontendContainerImageTag string = 'latest_waf_2025-09-18_898'

@description('Optional. The tags to apply to all deployed Azure resources.')
param tags resourceInput<'Microsoft.Resources/resourceGroups@2025-04-01'>.tags = {}

@description('Optional. Enable private networking for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enablePrivateNetworking bool = false

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Optional. Enable monitoring applicable resources, aligned with the Well Architected Framework recommendations. This setting enables Application Insights and Log Analytics and configures all the resources applicable resources to send logs. Defaults to false.')
param enableMonitoring bool =  false

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

@description('Optional: Existing Log Analytics Workspace Resource ID')
param existingLogAnalyticsWorkspaceId string = ''

@description('Optional. Use this parameter to use an existing AI project resource ID')
param existingAiFoundryAiProjectResourceId string = ''

@description('Optional. created by user name')
param createdBy string = contains(deployer(), 'userPrincipalName')? split(deployer().userPrincipalName, '@')[0]: deployer().objectId


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

var acrName = 'kmcontainerreg'
var baseUrl = 'https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/'
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
    tags: union(
      reference(
        resourceGroup().id, 
        '2021-04-01', 
        'Full'
      ).tags ?? {},
      {
        TemplateName: 'KM-Generic'
        Type: enablePrivateNetworking ? 'WAF' : 'Non-WAF'
        CreatedBy: createdBy
      },
      tags
    )
  }
}

#disable-next-line no-deployments-resources
resource avmTelemetry 'Microsoft.Resources/deployments@2024-03-01' = if (enableTelemetry) {
  name: '46d3xbcp.ptn.sa-multiagentcustauteng.${replace('-..--..-', '.', '-')}.${substring(uniqueString(deployment().name, location), 0, 4)}'
  properties: {
    mode: 'Incremental'
    template: {
      '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#'
      contentVersion: '1.0.0.0'
      resources: []
      outputs: {
        telemetry: {
          type: 'String'
          value: 'For more information, see https://aka.ms/avm/TelemetryInfo'
        }
      }
    }
  }
}

// ========== Log Analytics Workspace ========== //
// WAF best practices for Log Analytics: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-log-analytics
// WAF PSRules for Log Analytics: https://azure.github.io/PSRule.Rules.Azure/en/rules/resource/#azure-monitor-logs
var logAnalyticsWorkspaceResourceName = 'log-${solutionSuffix}'
module logAnalyticsWorkspace 'br/public:avm/res/operational-insights/workspace:0.12.0' = if (enableMonitoring && !useExistingLogAnalytics) {
  name: take('avm.res.operational-insights.workspace.${logAnalyticsWorkspaceResourceName}', 64)
  params: {
    name: logAnalyticsWorkspaceResourceName
    tags: tags
    location: location
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
    location: location
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
  name: take('module.network.${solutionSuffix}', 64)
  params: {
    resourcesName: solutionSuffix
    logAnalyticsWorkSpaceResourceId: logAnalyticsWorkspaceResourceId
    vmAdminUsername: vmAdminUsername ?? 'JumpboxAdminUser'
    vmAdminPassword: vmAdminPassword ?? 'JumpboxAdminP@ssw0rd1234!'
    vmSize: vmSize ?? 'Standard_DS2_v2' // Default VM size 
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// ========== Private DNS Zones ========== //
var privateDnsZones = [
  'privatelink.cognitiveservices.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.services.ai.azure.com'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.queue.${environment().suffixes.storage}'
  'privatelink.file.${environment().suffixes.storage}'
  'privatelink.dfs.${environment().suffixes.storage}'
  'privatelink.documents.azure.com'
  'privatelink.vaultcore.azure.net'
  'privatelink${environment().suffixes.sqlServerHostname}'
  'privatelink.search.windows.net'
]
// DNS Zone Index Constants
var dnsZoneIndex = {
  cognitiveServices: 0
  openAI: 1
  aiServices: 2
  storageBlob: 3
  storageQueue: 4
  storageFile: 5
  storageDfs: 6
  cosmosDB: 7
  keyVault: 8
  sqlServer: 9
  search: 10
}
// List of DNS zone indices that correspond to AI-related services.
var aiRelatedDnsZoneIndices = [
  dnsZoneIndex.cognitiveServices
  dnsZoneIndex.openAI
  dnsZoneIndex.aiServices
]

// ===================================================
// DEPLOY PRIVATE DNS ZONES
// - Deploys all zones if no existing Foundry project is used
// - Excludes AI-related zones when using with an existing Foundry project
// ===================================================
@batchSize(5)
module avmPrivateDnsZones 'br/public:avm/res/network/private-dns-zone:0.7.1' = [
  for (zone, i) in privateDnsZones: if (enablePrivateNetworking) {
    name: 'avm.res.network.private-dns-zone.${split(zone, '.')[1]}'
    params: {
      name: zone
      tags: tags
      enableTelemetry: enableTelemetry
      virtualNetworkLinks: [
        {
          name: take('vnetlink-${network!.outputs.vnetName}-${split(zone, '.')[1]}', 80)
          virtualNetworkResourceId: network!.outputs.vnetResourceId
        }
      ]
    }
  }
]

// ========== AVM WAF ========== //
// ========== User Assigned Identity ========== //
// WAF best practices for identity and access management: https://learn.microsoft.com/en-us/azure/well-architected/security/identity-access
var userAssignedIdentityResourceName = 'id-${solutionSuffix}'
module userAssignedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: take('avm.res.managed-identity.user-assigned-identity.${userAssignedIdentityResourceName}', 64)
  params: {
    name: userAssignedIdentityResourceName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// ========== SQL Operations User Assigned Identity ========== //
// Dedicated identity for backend SQL operations with limited permissions (db_datareader, db_datawriter)
var sqlUserAssignedIdentityResourceName = 'id-sql-${solutionSuffix}'
module sqlUserAssignedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: take('avm.res.managed-identity.user-assigned-identity.${sqlUserAssignedIdentityResourceName}', 64)
  params: {
    name: sqlUserAssignedIdentityResourceName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// ========== AVM WAF ========== //
// ========== Key Vault Module ========== //
var keyVaultName = 'kv-${solutionSuffix}'
module keyvault 'br/public:avm/res/key-vault/vault:0.12.1' = {
  name: take('avm.res.key-vault.vault.${keyVaultName}', 64)
  params: {
    name: keyVaultName
    location: location
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
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : []
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
            subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
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
        value: storageAccount.outputs.primaryAccessKey
      }
      {
        name: 'AZURE-SEARCH-ENDPOINT'
        value: 'https://${searchSearchServices.outputs.name}.search.windows.net'
      }
      {
        name: 'AZURE-SEARCH-SERVICE'
        value: searchSearchServices.outputs.name
      }
      {
        name: 'AZURE-OPENAI-ENDPOINT'
        value: !empty(existingOpenAIEndpoint) ? existingOpenAIEndpoint : 'https://${aiFoundryAiServicesResourceName}.openai.azure.com/'
      }
      {
        name: 'COG-SERVICES-ENDPOINT'
        value: !empty(existingOpenAIEndpoint) ? existingOpenAIEndpoint : aiFoundryAiServices.outputs.endpoint
      }
      {
        name: 'AZURE-OPENAI-SEARCH-PROJECT'
        value: !empty(existingAiFoundryAiProjectResourceId) ? existingAIProjectName : aiFoundryAiServicesAiProjectResourceName
      }
      {
        name: 'AZURE-OPENAI-INFERENCE-ENDPOINT'
        value: ''
      }
      {
        name: 'AZURE-OPENAI-DEPLOYMENT-MODEL'
        value: gptModelName
      }
      {
        name: 'AZURE-OPENAI-PREVIEW-API-VERSION'
        value: azureOpenAIApiVersion
      }
      {
        name: 'AZURE-OPENAI-CU-ENDPOINT'
        value: cognitiveServicesCu.outputs.endpoints['OpenAI Language Model Instance API']
      }
      {
        name: 'AZURE-OPENAI-CU-VERSION'
        value: '?api-version=2024-12-01-preview'
      }
      {
        name: 'AZURE-SEARCH-INDEX'
        value: 'transcripts_index'
      }
      {
        name: 'COG-SERVICES-NAME'
        value: aiFoundryAiServicesResourceName
      }
      {
        name: 'AZURE-OPENAI-INFERENCE-ENDPOINT'
        value: ''
      }
      {
        name: 'AZURE-OPENAI-INFERENCE-ENDPOINT'
        value: ''
      }
      {
        name: 'AZURE-OPENAI-EMBEDDING-MODEL'
        value: embeddingModel
      }
      {
        name: 'SQLDB-SERVER'
        value: 'sql-${solutionSuffix}${environment().suffixes.sqlServerHostname}'
      }
      {
        name: 'SQLDB-DATABASE'
        value: 'sqldb-${solutionSuffix}'
      }
    ]
    enableTelemetry: enableTelemetry
  }
}

// ==========AI Foundry and related resources ========== //
// ========== AI Foundry: AI Services ========== //
// WAF best practices for Open AI: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-openai

var existingOpenAIEndpoint = !empty(existingAiFoundryAiProjectResourceId) ? format('https://{0}.openai.azure.com/', split(existingAiFoundryAiProjectResourceId, '/')[8]) : ''
var existingProjEndpoint = !empty(existingAiFoundryAiProjectResourceId) ? format('https://{0}.services.ai.azure.com/api/projects/{1}', split(existingAiFoundryAiProjectResourceId, '/')[8], split(existingAiFoundryAiProjectResourceId, '/')[10]) : ''
var existingAIServicesName = !empty(existingAiFoundryAiProjectResourceId) ? split(existingAiFoundryAiProjectResourceId, '/')[8] : ''
var existingAIProjectName = !empty(existingAiFoundryAiProjectResourceId) ? split(existingAiFoundryAiProjectResourceId, '/')[10] : ''

var aiFoundryAiServicesSubscriptionId = useExistingAiFoundryAiProject
  ? split(existingAiFoundryAiProjectResourceId, '/')[2]
  : subscription().id
var useExistingAiFoundryAiProject = !empty(existingAiFoundryAiProjectResourceId)
var aiFoundryAiServicesResourceGroupName = useExistingAiFoundryAiProject
  ? split(existingAiFoundryAiProjectResourceId, '/')[4]
  : 'rg-${solutionSuffix}'
var aiFoundryAiServicesResourceName = useExistingAiFoundryAiProject
  ? split(existingAiFoundryAiProjectResourceId, '/')[8]
  : 'aif-${solutionSuffix}'
var aiFoundryAiProjectResourceName = useExistingAiFoundryAiProject
  ? split(existingAiFoundryAiProjectResourceId, '/')[10]
  : 'proj-${solutionSuffix}' 

// NOTE: Required version 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' not available in AVM
// var aiFoundryAiServicesResourceName = 'aif-${solutionSuffix}'
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

resource existingAiFoundryAiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = if (useExistingAiFoundryAiProject) {
  name: aiFoundryAiServicesResourceName
  scope: resourceGroup(aiFoundryAiServicesSubscriptionId, aiFoundryAiServicesResourceGroupName)
}

resource existingAiFoundryAiServicesProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = if (useExistingAiFoundryAiProject) {
  name: aiFoundryAiProjectResourceName
  parent: existingAiFoundryAiServices
}


//TODO: update to AVM module when AI Projects and AI Projects RBAC are supported
module aiFoundryAiServices 'modules/ai-services.bicep' = if (aiFoundryAIservicesEnabled) {
  name: take('avm.res.cognitive-services.account.${aiFoundryAiServicesResourceName}', 64)
  params: {
    name: aiFoundryAiServicesResourceName
    location: aiServiceLocation
    tags: tags
    existingFoundryProjectResourceId: existingAiFoundryAiProjectResourceId
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
      bypass: 'AzureServices'
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
    privateEndpoints: (enablePrivateNetworking &&  empty(existingAiFoundryAiProjectResourceId))
      ? ([
          {
            name: 'pep-${aiFoundryAiServicesResourceName}'
            customNetworkInterfaceName: 'nic-${aiFoundryAiServicesResourceName}'
            subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
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
// NOTE: Required version 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' not available in AVM
module cognitiveServicesCu 'br/public:avm/res/cognitive-services/account:0.10.1' = {
  name: take('avm.res.cognitive-services.account.${aiFoundryAiServicesCUResourceName}', 64)
  params: {
    name: aiServicesName_cu
    location: contentUnderstandingLocation
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
    privateEndpoints: (enablePrivateNetworking)
      ? ([
          {
            name: 'pep-${aiFoundryAiServicesCUResourceName}'
            customNetworkInterfaceName: 'nic-${aiFoundryAiServicesCUResourceName}'
            subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'ai-services-cu-dns-zone-cognitiveservices'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
                }
                {
                  name: 'ai-services-cu-dns-zone-openai'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.openAI]!.outputs.resourceId
                }
                {
                  name: 'ai-services-cu-dns-zone-aiservices'
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
    ]
  }
}

// ========== AVM WAF ========== //
// ========== AI Foundry: AI Search ========== //
var aiSearchName = 'srch-${solutionSuffix}'
module searchSearchServices 'br/public:avm/res/search/search-service:0.11.1' = {
  name: take('avm.res.search.search-service.${aiSearchName}', 64)
  params: {
    // Required parameters
    name: aiSearchName
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
    diagnosticSettings: enableMonitoring ? [
      {
        workspaceResourceId: logAnalyticsWorkspaceResourceId
      }
    ] : null
    disableLocalAuth: false
    hostingMode: 'default'
    managedIdentities: {
      systemAssigned: true
    }
    networkRuleSet: {
      bypass: 'AzureServices'
      ipRules: []
    }
    roleAssignments: [
      {
        roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: '8ebe5a00-799e-43f5-93ac-243d3dce84a7' //'Search Index Data Contributor'
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: '1407120a-92aa-4202-b7e9-c0e197c71c8f' // Search Index Data Reader
        principalId: !useExistingAiFoundryAiProject ? aiFoundryAiServices.outputs.aiProjectInfo.aiprojectSystemAssignedMIPrincipalId : existingAiFoundryAiServicesProject!.identity.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0' // Search Service Contributor
        principalId: !useExistingAiFoundryAiProject ? aiFoundryAiServices.outputs.aiProjectInfo.aiprojectSystemAssignedMIPrincipalId : existingAiFoundryAiServicesProject!.identity.principalId
        principalType: 'ServicePrincipal'
      }
    ]
    partitionCount: 1
    replicaCount: 1
    sku: 'standard'
    semanticSearch: 'free'
    // Use the deployment tags provided to the template
    tags: tags
    publicNetworkAccess: 'Enabled' //enablePrivateNetworking ? 'Disabled' : 'Enabled'
    privateEndpoints: false //enablePrivateNetworking
    ? [
        {
          name: 'pep-${aiSearchName}'
          customNetworkInterfaceName: 'nic-${aiSearchName}'
          privateDnsZoneGroup: {
            privateDnsZoneGroupConfigs: [
              { privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.search]!.outputs.resourceId }
            ]
          }
          service: 'searchService'
          subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
        }
      ]
    : []
  }
}

// ========== Search Service to AI Services Role Assignment ========== //
resource searchServiceToAiServicesRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingAiFoundryAiProject){
  name: guid(aiSearchName, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd', aiFoundryAiServicesResourceName)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd') // Cognitive Services OpenAI User
    principalId: searchSearchServices.outputs.systemAssignedMIPrincipalId!
    principalType: 'ServicePrincipal'
  }
}

resource projectAISearchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = if (!useExistingAiFoundryAiProject){
  name: '${aiFoundryAiServicesResourceName}/${aiFoundryAiServicesAiProjectResourceName}/${aiSearchName}'
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${aiSearchName}.search.windows.net'
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: searchSearchServices.outputs.resourceId
      location: searchSearchServices.outputs.location
    }
  }
}

module existing_AIProject_SearchConnectionModule 'modules/deploy_aifp_aisearch_connection.bicep' = if (useExistingAiFoundryAiProject) {
  name: 'aiProjectSearchConnectionDeployment'
  scope: resourceGroup(aiFoundryAiServicesSubscriptionId, aiFoundryAiServicesResourceGroupName)
  params: {
    existingAIProjectName: aiFoundryAiProjectResourceName
    existingAIFoundryName: aiFoundryAiServicesResourceName
    aiSearchName: aiSearchName
    aiSearchResourceId: searchSearchServices.outputs.resourceId
    aiSearchLocation: searchSearchServices.outputs.location
    aiSearchConnectionName: aiSearchName
  }
}

// Role assignment for existing AI Services scenario
module searchServiceToExistingAiServicesRoleAssignment 'modules/role-assignment.bicep' = if (useExistingAiFoundryAiProject) {
  name: 'searchToExistingAiServices-roleAssignment'
  scope: resourceGroup(aiFoundryAiServicesSubscriptionId, aiFoundryAiServicesResourceGroupName)
  params: {
    principalId: searchSearchServices.outputs.systemAssignedMIPrincipalId!
    roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User
    targetResourceName: aiFoundryAiServices.outputs.name
  }
}

// ========== AVM WAF ========== //
// ========== Storage account module ========== //
var storageAccountName = 'st${solutionSuffix}'
module storageAccount 'br/public:avm/res/storage/storage-account:0.20.0' = {
  name: take('avm.res.storage.storage-account.${storageAccountName}', 64)
  params: {
    name: storageAccountName
    location: location
    managedIdentities: { 
      systemAssigned: true
      userAssignedResourceIds: [ userAssignedIdentity!.outputs.resourceId ]
    }
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    accessTier: 'Hot'
    enableTelemetry: enableTelemetry
    tags: tags
    enableHierarchicalNamespace: true
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        roleDefinitionIdOrName: 'Storage Blob Data Contributor'
        principalType: 'ServicePrincipal'
      }
      {
        principalId: userAssignedIdentity.outputs.principalId
        roleDefinitionIdOrName: 'Storage Account Contributor'
        principalType: 'ServicePrincipal'
      }
      {
        principalId: userAssignedIdentity.outputs.principalId
        roleDefinitionIdOrName: 'Storage File Data Privileged Contributor'
        principalType: 'ServicePrincipal'
      }
    ]
    networkAcls: {
      bypass: 'AzureServices, Logging, Metrics'
      defaultAction: 'Allow'
      virtualNetworkRules: []
    }
    allowSharedKeyAccess: true
    allowBlobPublicAccess: true
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    privateEndpoints: enablePrivateNetworking ? [
      {
        name: 'pep-blob-${solutionSuffix}'
        service: 'blob'
        subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
        privateDnsZoneGroup: {
          privateDnsZoneGroupConfigs: [
            {
              name: 'storage-dns-zone-group-blob'
              privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageBlob]!.outputs.resourceId
            }
          ]
        }
      }
      {
        name: 'pep-queue-${solutionSuffix}'
        service: 'queue'
        subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
        privateDnsZoneGroup: {
          privateDnsZoneGroupConfigs: [
            {
              name: 'storage-dns-zone-group-queue'
              privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageQueue]!.outputs.resourceId
            }
          ]
        }
      }
      {
        name: 'pep-file-${solutionSuffix}'
        service: 'file'
        subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
        privateDnsZoneGroup: {
          privateDnsZoneGroupConfigs: [
            {
              name: 'storage-dns-zone-group-file'
              privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageFile]!.outputs.resourceId
            }
          ]
        }
      }
      {
        name: 'pep-dfs-${solutionSuffix}'
        service: 'dfs'
        subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
        privateDnsZoneGroup: {
          privateDnsZoneGroupConfigs: [
            {
              name: 'storage-dns-zone-group-dfs'
              privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageDfs]!.outputs.resourceId
            }
          ]
        }
      }
    ] : []
    blobServices: {
      corsRules: []
      deleteRetentionPolicyEnabled: false
      changeFeedEnabled: false
      restorePolicyEnabled: false
      isVersioningEnabled: false
      containerDeleteRetentionPolicyEnabled: false
      lastAccessTimeTrackingPolicy: {
        enable: false
      }
      containers: [
        {
          name: 'data'
        }
      ]
    }
  }
}

//========== AVM WAF ========== //
//========== Cosmos DB module ========== //
var cosmosDbResourceName = 'cosmos-${solutionSuffix}'
var cosmosDbDatabaseName = 'db_conversation_history'
var collectionName = 'conversations'
module cosmosDb 'br/public:avm/res/document-db/database-account:0.15.0' = {
  name: take('avm.res.document-db.database-account.${cosmosDbResourceName}', 64)
  params: {
    // Required parameters
    name: cosmosDbResourceName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    sqlDatabases: [
      {
        name: cosmosDbDatabaseName
        containers: [
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
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
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
            subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
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
            locationName: location
          }
          {
            failoverPriority: 1
            isZoneRedundant: true
            locationName: cosmosDbHaLocation
          }
        ]
      : [
          {
            locationName: location
            failoverPriority: 0
            isZoneRedundant: false
          }
        ]
  }
  dependsOn: [storageAccount]
}

//========== AVM WAF ========== //
//========== SQL Database module ========== //
var sqlServerResourceName = 'sql-${solutionSuffix}'
var sqlDbModuleName = 'sqldb-${solutionSuffix}'
module sqlDBModule 'br/public:avm/res/sql/server:0.20.1' = {
  name: take('avm.res.sql.server.${sqlServerResourceName}', 64)
  params: {
    // Required parameters
    name: sqlServerResourceName
    // Non-required parameters
    administrators: {
      azureADOnlyAuthentication: true
      login: userAssignedIdentity.outputs.name
      principalType: 'Application'
      sid: userAssignedIdentity.outputs.principalId
      tenantId: subscription().tenantId
    }
    connectionPolicy: 'Redirect'
    databases: [
      {
        availabilityZone: enableRedundancy ? 1 : -1
        collation: 'SQL_Latin1_General_CP1_CI_AS'
        diagnosticSettings: enableMonitoring
          ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }]
          : null
        licenseType: 'LicenseIncluded'
        maxSizeBytes: 34359738368
        name: sqlDbModuleName
        minCapacity: '1'
        sku: {
          name: 'GP_S_Gen5'
          tier: 'GeneralPurpose'
          family: 'Gen5'
          capacity: 2
        }
        zoneRedundant: enableRedundancy ? true : false
      }
    ]
    location: secondaryLocation
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
            subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
            tags: tags
          }
        ]
      : []
    firewallRules: (!enablePrivateNetworking) ? [
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
    ] : []
    tags: tags
  }
}

//========== AVM WAF ========== //
//========== Deployment script to upload data ========== //
module uploadFiles 'br/public:avm/res/resources/deployment-script:0.5.1' = {
  name: take('avm.res.resources.deployment-script.uploadFiles', 64)
  params: {
    kind: 'AzureCLI'
    name: 'copy_demo_Data'
    azCliVersion: '2.52.0'
    cleanupPreference: 'Always'
    location: enablePrivateNetworking ? location : secondaryLocation
    managedIdentities: {
      userAssignedResourceIds: [
        userAssignedIdentity.outputs.resourceId
      ]
    }
    retentionInterval: 'P1D'
    runOnce: true
    primaryScriptUri: '${baseUrl}infra/scripts/copy_kb_files.sh'
    arguments: '${storageAccount.outputs.name} data ${baseUrl} ${userAssignedIdentity.outputs.clientId}'
    storageAccountResourceId: storageAccount.outputs.resourceId
    subnetResourceIds: enablePrivateNetworking ? [
      network!.outputs.subnetDeploymentScriptsResourceId
    ] : null
    tags: tags
    timeout: 'PT1H'
  }
}

//========== AVM WAF ========== //
//========== Deployment script to create index ========== //
module createIndex 'br/public:avm/res/resources/deployment-script:0.5.1' = {
  name: take('avm.res.resources.deployment-script.createIndex', 64)
  params: {
    // Required parameters
    kind: 'AzureCLI'
    name: 'create_search_indexes'
    // Non-required parameters
    azCliVersion: '2.52.0'
    location: enablePrivateNetworking ? location : secondaryLocation
    managedIdentities: {
      userAssignedResourceIds: [
        userAssignedIdentity.outputs.resourceId
      ]
    }
    runOnce: true
    primaryScriptUri: '${baseUrl}infra/scripts/run_create_index_scripts.sh'
    arguments: '${baseUrl} ${keyvault.outputs.name} ${userAssignedIdentity.outputs.clientId}'
    tags: tags
    timeout: 'PT1H'
    retentionInterval: 'P1D'
    cleanupPreference: 'OnSuccess'
    storageAccountResourceId: storageAccount.outputs.resourceId
    subnetResourceIds: enablePrivateNetworking ? [
      network!.outputs.subnetDeploymentScriptsResourceId
    ] : null
  }
  dependsOn:[sqlDBModule,uploadFiles]
}

var databaseRoles = [
  'db_datareader'
  'db_datawriter'
]
//========== Deployment script to create Sql User and Role  ========== //
module createSqlUserAndRole 'br/public:avm/res/resources/deployment-script:0.5.1' = {
  name: take('avm.res.resources.deployment-script.createSqlUserAndRole', 64)
  params: {
    // Required parameters
    kind: 'AzurePowerShell'
    name: 'create_sql_user_and_role'
    // Non-required parameters
    azPowerShellVersion: '11.0'
    location: enablePrivateNetworking ? location : secondaryLocation
    managedIdentities: {
      userAssignedResourceIds: [
        userAssignedIdentity.outputs.resourceId
      ]
    }
    runOnce: true
    arguments: join(
      [
        '-SqlServerName \'${sqlServerResourceName}\''
        '-SqlDatabaseName \'${sqlDbModuleName}\''
        '-ClientId \'${sqlUserAssignedIdentity.outputs.clientId}\''
        '-DisplayName \'${sqlUserAssignedIdentity.outputs.name}\''
        '-DatabaseRoles \'${join(databaseRoles, ',')}\''
      ],
      ' '
    )
    scriptContent: loadTextContent('./scripts/add_user_scripts/create-sql-user-and-role.ps1')
    tags: tags
    timeout: 'PT1H'
    retentionInterval: 'PT1H'
    cleanupPreference: 'OnSuccess'
    storageAccountResourceId: storageAccount.outputs.resourceId
    subnetResourceIds: enablePrivateNetworking ? [
      network!.outputs.subnetDeploymentScriptsResourceId
    ] : null
  }
  dependsOn:[sqlDBModule]
}

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
    location: location
    reserved: true
    kind: 'linux'
    // WAF aligned configuration for Monitoring
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
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
var backendWebSiteResourceName = 'api-${solutionSuffix}'
module webSiteBackend 'modules/web-sites.bicep' = {
  name: take('module.web-sites.${backendWebSiteResourceName}', 64)
  params: {
    name: backendWebSiteResourceName
    tags: tags
    location: location
    kind: 'app,linux,container'
    serverFarmResourceId: webServerFarm.?outputs.resourceId
    managedIdentities: {
      systemAssigned: true
      userAssignedResourceIds: [
        userAssignedIdentity.outputs.resourceId
      ]
    }
    siteConfig: {
      linuxFxVersion: 'DOCKER|${backendContainerRegistryHostname}/${backendContainerImageName}:${backendContainerImageTag}'
      minTlsVersion: '1.2'
    }
    configs: [
      {
        name: 'appsettings'
        properties: {
          REACT_APP_LAYOUT_CONFIG: reactAppLayoutConfig
          AZURE_OPENAI_DEPLOYMENT_MODEL: gptModelName
          AZURE_OPENAI_ENDPOINT: !empty(existingOpenAIEndpoint) ? existingOpenAIEndpoint : 'https://${aiFoundryAiServices.outputs.name}.openai.azure.com/'
          AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
          AZURE_OPENAI_RESOURCE: aiFoundryAiServices.outputs.name
          AZURE_AI_AGENT_ENDPOINT: !empty(existingProjEndpoint) ? existingProjEndpoint : aiFoundryAiServices.outputs.aiProjectInfo.apiEndpoint
          AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
          AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
          USE_CHAT_HISTORY_ENABLED: 'True'
          AZURE_COSMOSDB_ACCOUNT: cosmosDb.outputs.name
          AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: collectionName
          AZURE_COSMOSDB_DATABASE: cosmosDbDatabaseName
          AZURE_COSMOSDB_ENABLE_FEEDBACK: 'True'
          SQLDB_DATABASE: 'sqldb-${solutionSuffix}'
          SQLDB_SERVER: '${sqlDBModule.outputs.name }${environment().suffixes.sqlServerHostname}'
          SQLDB_USER_MID: sqlUserAssignedIdentity.outputs.clientId
          AZURE_AI_SEARCH_ENDPOINT: 'https://${aiSearchName}.search.windows.net'
          AZURE_AI_SEARCH_INDEX: 'call_transcripts_index'
          AZURE_AI_SEARCH_CONNECTION_NAME: aiSearchName
          USE_AI_PROJECT_CLIENT: 'True'
          DISPLAY_CHART_DEFAULT: 'False'
          APPLICATIONINSIGHTS_CONNECTION_STRING: enableMonitoring ? applicationInsights!.outputs.connectionString : ''
          DUMMY_TEST: 'True'
          SOLUTION_NAME: solutionSuffix
          APP_ENV: 'Prod'
          AZURE_CLIENT_ID: userAssignedIdentity.outputs.clientId
        }
        // WAF aligned configuration for Monitoring
        applicationInsightResourceId: enableMonitoring ? applicationInsights!.outputs.resourceId : null
      }
    ]
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    // WAF aligned configuration for Private Networking
    vnetRouteAllEnabled: enablePrivateNetworking ? true : false
    vnetImagePullEnabled: enablePrivateNetworking ? true : false
    virtualNetworkSubnetId: enablePrivateNetworking ? network!.outputs.subnetWebResourceId : null
    publicNetworkAccess: 'Enabled'
  }
}

// ========== Web App module ========== //
// WAF best practices for Web Application Services: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/app-service-web-apps
//NOTE: AVM module adds 1 MB of overhead to the template. Keeping vanilla resource to save template size.
var webSiteResourceName = 'app-${solutionSuffix}'
module webSiteFrontend 'modules/web-sites.bicep' = {
  name: take('module.web-sites.${webSiteResourceName}', 64)
  params: {
    name: webSiteResourceName
    tags: tags
    location: location
    kind: 'app,linux,container'
    serverFarmResourceId: webServerFarm.outputs.resourceId
    siteConfig: {
      linuxFxVersion: 'DOCKER|${frontendContainerRegistryHostname}/${frontendContainerImageName}:${frontendContainerImageTag}'
      minTlsVersion: '1.2'
    }
    configs: [
      {
        name: 'appsettings'
        properties: {
          APP_API_BASE_URL: 'https://api-${solutionSuffix}.azurewebsites.net'
        }
        applicationInsightResourceId: enableMonitoring ? applicationInsights!.outputs.resourceId : null
      }
    ]
    vnetRouteAllEnabled: enablePrivateNetworking ? true : false
    vnetImagePullEnabled: enablePrivateNetworking ? true : false
    virtualNetworkSubnetId: enablePrivateNetworking ? network!.outputs.subnetWebResourceId : null
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    publicNetworkAccess: 'Enabled'
  }
}

@description('Contains Solution Name.')
output SOLUTION_NAME string = solutionSuffix

@description('Contains Resource Group Name.')
output RESOURCE_GROUP_NAME string = resourceGroup().name

@description('Contains Resource Group Location.')
output RESOURCE_GROUP_LOCATION string = location

@description('Contains Azure Content Understanding Location.')
output AZURE_CONTENT_UNDERSTANDING_LOCATION string = contentUnderstandingLocation

// @description('Contains Azure Secondary Location.')
// output AZURE_SECONDARY_LOCATION string = secondaryLocation

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
output AZURE_AI_SEARCH_CONNECTION_NAME string = aiSearchName

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
output AZURE_OPENAI_ENDPOINT string = 'https://${aiFoundryAiServices.outputs.name}.openai.azure.com/'

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
output SQLDB_USER_MID string = sqlUserAssignedIdentity.outputs.clientId

@description('Contains AI project client usage setting.')
output USE_AI_PROJECT_CLIENT string = 'False'

@description('Contains chat history enablement setting.')
output USE_CHAT_HISTORY_ENABLED string = 'True'

@description('Contains default chart display setting.')
output DISPLAY_CHART_DEFAULT string = 'False'

@description('Contains Azure AI Agent endpoint URL.')
output AZURE_AI_AGENT_ENDPOINT string = !empty(existingProjEndpoint) ? existingProjEndpoint : aiFoundryAiServices.outputs.aiProjectInfo.apiEndpoint

@description('Contains Azure AI Agent model deployment name.')
output AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME string = gptModelName

@description('Contains Azure Container Registry name.')
output ACR_NAME string = acrName

@description('Contains Azure environment image tag.')
output AZURE_ENV_IMAGETAG string = backendContainerImageTag

@description('Contains existing AI project resource ID.')
output AZURE_EXISTING_AI_PROJECT_RESOURCE_ID string = existingAiFoundryAiProjectResourceId

@description('Contains Application Insights connection string.')
output APPLICATIONINSIGHTS_CONNECTION_STRING string = enableMonitoring ? applicationInsights!.outputs.connectionString : ''

@description('Contains API application URL.')
output API_APP_URL string = 'https://api-${solutionSuffix}.azurewebsites.net'

@description('Contains web application URL.')
output WEB_APP_URL string = 'https://app-${solutionSuffix}.azurewebsites.net'
