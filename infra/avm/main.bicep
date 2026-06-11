// ============================================================================
// main.bicep — Orchestrator
// Description: Pure orchestrator for Conversation Knowledge Mining solution. Calls modules to deploy resources.
//              All resource names are derived from params — no hardcoded names.
//              This file only calls modules; no inline resource definitions.
//              Supports WAF-aligned deployment via feature flags.
// ============================================================================
targetScope = 'resourceGroup'

// ============================================================================
// Parameters — Core
// ============================================================================

@minLength(3)
@maxLength(16)
@description('Optional. A unique application/solution name used as base for all resource naming.')
param solutionName string = 'kmgen'

@maxLength(5)
@description('Optional. A unique text suffix appended to resource names for uniqueness.')
param solutionUniqueText string = substring(uniqueString(subscription().id, resourceGroup().name, solutionName), 0, 5)

@metadata({ azd: { type: 'location' } })
@description('Required. Azure region for all services. Regions are restricted to guarantee compatibility with paired regions and replica locations for data redundancy and failover scenarios based on articles [Azure regions list](https://learn.microsoft.com/azure/reliability/regions-list) and [Azure Database for MySQL Flexible Server - Azure Regions](https://learn.microsoft.com/azure/mysql/flexible-server/overview#azure-regions).')
@allowed(['australiaeast','centralus','eastasia','eastus2','japaneast','northeurope','southeastasia','uksouth'])

param location string

@description('Optional. Secondary location for database resources.')
param secondaryLocation string = 'eastus2'


@allowed(['australiaeast','eastus','eastus2','japaneast','southcentralus','swedencentral','uksouth','westeurope','westus','westus3'])
@metadata({
  azd:{
    type: 'location'
    usageName: [
      'OpenAI.GlobalStandard.gpt-4o-mini,150'
      'OpenAI.GlobalStandard.text-embedding-3-small,80'
    ]
  }
})
@description('Required. Location for AI Foundry and model deployments.')
param azureAiServiceLocation string

@minLength(1)
@description('Required. Industry use case for deployment.')
@allowed([
  'telecom'
  'IT_helpdesk'
])
param usecase string

@description('Optional. Location for AI Search service deployment.')
param searchServiceLocation string = location

// ============================================================================
// Parameters — WAF Feature Flags
// ============================================================================

@description('Optional. Tags to apply to all resources.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for AVM modules.')
param enableTelemetry bool = true

@description('Optional. Enable monitoring for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enableMonitoring bool = false

@description('Optional. Enable private networking for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enablePrivateNetworking bool = false

@description('Optional. Enable scalability for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enableScalability bool = false

@description('Optional. Enable redundancy for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enableRedundancy bool = false

// ============================================================================
// Parameters — VM (applicable when enablePrivateNetworking = true)
// ============================================================================

@secure()
@description('Optional. The user name for the administrator account of the virtual machine. Required by Azure at provisioning time but not used for login when Entra ID is enabled.')
param vmAdminUsername string?

@secure()
@description('Optional. The password for the administrator account of the virtual machine. Auto-generated if not provided. Not used for login when Entra ID is enabled.')
param vmAdminPassword string?

@description('Optional. The size of the virtual machine. Defaults to Standard_D2s_v5.')
param vmSize string = 'Standard_D2s_v5'

// ============================================================================
// Parameters — AI Configuration
// ============================================================================

@allowed(['Standard', 'GlobalStandard'])
@description('Optional. GPT model deployment type.')
param deploymentType string = 'GlobalStandard'

@description('Optional. Name of the GPT model to deploy.')
param gptModelName string = 'gpt-4o-mini'

@description('Optional. Version of the GPT model to deploy.')
param gptModelVersion string = '2024-07-18'

@minValue(10)
@description('Optional. Capacity of the GPT deployment (TPM in thousands).')
param gptDeploymentCapacity int = 150

@description('Optional. Name of the embedding model to deploy.')
@allowed(['text-embedding-3-small'])
param embeddingModel string = 'text-embedding-3-small'

@minValue(10)
@description('Optional. Capacity of the embedding model deployment.')
param embeddingDeploymentCapacity int = 80

@description('Optional. Azure AI Agent API version.')
param azureAiAgentApiVersion string = '2025-05-01'

@description('Optional. Version of Content Understanding API.')
param azureContentUnderstandingApiVersion string = '2025-11-01'

// ============================================================================
// Parameters — Compute
// ============================================================================

@description('Optional. Docker image tag for app deployments.')
param imageTag string = 'latest_afv2'

@description('Optional. Name of the Azure Container Registry.')
param containerRegistryName string = 'kmcontainerreg'

@description('Optional. Container Registry hostname where the backend image is located.')
param backendContainerRegistryHostname string = '${containerRegistryName}.azurecr.io'

@description('Optional. Backend container image name.')
param backendContainerImageName string = 'km-api'

@description('Optional. Backend container image tag.')
param backendContainerImageTag string = imageTag

@description('Optional. Container Registry hostname where the frontend image is located.')
param frontendContainerRegistryHostname string = '${containerRegistryName}.azurecr.io'

@description('Optional. Frontend container image name.')
param frontendContainerImageName string = 'km-app'

@description('Optional. Frontend container image tag.')
param frontendContainerImageTag string = imageTag

@allowed(['F1', 'D1', 'B1', 'B2', 'B3', 'S1', 'S2', 'S3', 'P1', 'P2', 'P3', 'P1v3', 'P1v4'])
@description('Optional. App Service Plan SKU.')
param appServicePlanSku string = 'B3'

// ============================================================================
// Parameters — Feature Flags
// ============================================================================

@description('Optional. Enable chat history storage.')
param useChatHistoryEnabled bool = true

// ============================================================================
// Parameters — Existing Resources
// ============================================================================

@description('Optional. Resource ID of an existing Log Analytics workspace (empty = create new).')
param existingLogAnalyticsWorkspaceId string = ''

@description('Optional. Resource ID of an existing AI Foundry project (empty = create new).')
param existingFoundryProjectResourceId string = ''

// ============================================================================
// Parameters — Identity
// ============================================================================

@allowed(['User', 'ServicePrincipal'])
@description('Optional. Principal type of the deploying user.')
param deployingUserPrincipalType string = 'User'

// ============================================================================
// Variables
// ============================================================================

var solutionSuffix = toLower(trim(replace(replace(replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''), ' ', ''), '*', '')))
var deployerInfo = deployer()
var deployingUserPrincipalId = deployerInfo.objectId
var createdBy = contains(deployerInfo, 'userPrincipalName') ? split(deployerInfo.userPrincipalName, '@')[0] : deployerInfo.objectId
var useExistingAIProject = !empty(existingFoundryProjectResourceId)
var useChatHistoryEnabledSetting = useChatHistoryEnabled ? 'True' : 'False'

// ========== Tags: merge caller-supplied tags with standard metadata (matching old infra) ========== //
var existingTags = resourceGroup().tags ?? {}
var resourceTags = union(existingTags, tags, {
  TemplateName: 'KM-Generic'
  CreatedBy: createdBy
  DeploymentName: deployment().name
  Type: enablePrivateNetworking ? 'WAF' : 'Non-WAF'
  UseCase: usecase
})

// ========== WAF: Region pairs for redundancy (Log Analytics replication) ========== //
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
var replicaLocation = replicaRegionPairs[location]

// ========== WAF: Region pairs for Cosmos DB zone-redundant HA ========== //
var cosmosDbHaRegionPairs = {
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
var cosmosDbHaLocation = cosmosDbHaRegionPairs[location]

// ========== WAF: Diagnostic settings helper — reused across modules ========== //
var monitoringDiagnosticSettings = enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : []

// ========== WAF: Private DNS zones for private endpoints ========== //
var privateDnsZones = [
  'privatelink.cognitiveservices.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.services.ai.azure.com'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.queue.${environment().suffixes.storage}'
  'privatelink.file.${environment().suffixes.storage}'
  'privatelink.dfs.${environment().suffixes.storage}'
  'privatelink.documents.azure.com'
  'privatelink${environment().suffixes.sqlServerHostname}'
  'privatelink.search.windows.net'
  'privatelink.azurewebsites.net'
]
var dnsZoneIndex = {
  cognitiveServices: 0
  openAI: 1
  aiServices: 2
  storageBlob: 3
  storageQueue: 4
  storageFile: 5
  storageDfs: 6
  cosmosDB: 7
  sqlServer: 8
  search: 9
  webApp: 10
}

// ========== Resource naming (parameterized — no abbreviations.json dependency) ========== //
// Resource names for generic modules are now derived inside each module from solutionName/solutionSuffix.

// ========== Model deployments configuration ========== //
var aiModelDeployments = [
  {
    name: gptModelName
    model: gptModelName
    sku: { name: deploymentType, capacity: gptDeploymentCapacity }
    version: gptModelVersion
    raiPolicyName: 'Microsoft.Default'
  }
  {
    name: embeddingModel
    model: embeddingModel
    sku: { name: 'GlobalStandard', capacity: embeddingDeploymentCapacity }
    version: '1'
    raiPolicyName: 'Microsoft.Default'
  }
]

// ============================================================================
// Resource Group Tags (matching old infra)
// ============================================================================

resource resourceGroupTags 'Microsoft.Resources/tags@2024-11-01' = {
  name: 'default'
  properties: {
    tags: resourceTags
  }
}

// ============================================================================
// Module: Monitoring
// ============================================================================

var useExistingLogAnalytics = !empty(existingLogAnalyticsWorkspaceId)

// Existing workspace reference (for cross-subscription support)
resource existingLogAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2025-07-01' existing = if (useExistingLogAnalytics) {
  name: split(existingLogAnalyticsWorkspaceId, '/')[8]
  scope: resourceGroup(split(existingLogAnalyticsWorkspaceId, '/')[2], split(existingLogAnalyticsWorkspaceId, '/')[4])
}

 //  ========== Log Analytics Workspace module ========== //
module log_analytics './modules/monitoring/log-analytics.bicep' = if (enableMonitoring && !useExistingLogAnalytics) {
  name: take('module.log-analytics.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    retentionInDays: 365
    publicNetworkAccessForIngestion: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    publicNetworkAccessForQuery: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    enableReplication: enableRedundancy
    replicationLocation: enableRedundancy ? replicaLocation : ''
    dailyQuotaGb: enableRedundancy ? '150' : ''
    dataSources: enablePrivateNetworking ? [
      {
        tags: tags
        eventLogName: 'Application'
        eventTypes: [{ eventType: 'Error' }, { eventType: 'Warning' }, { eventType: 'Information' }]
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
    ] : []
  }
}

// ========== Resolve workspace resource ID and name — existing or new ========== //
var logAnalyticsWorkspaceResourceId = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspace.id
  : (enableMonitoring ? log_analytics!.outputs.resourceId : '')
var logAnalyticsWorkspaceName = useExistingLogAnalytics
  ? split(existingLogAnalyticsWorkspaceId, '/')[8]
  : (enableMonitoring ? log_analytics!.outputs.name : '')

// ========== App Insights module ========== //
module app_insights './modules/monitoring/app-insights.bicep' = if (enableMonitoring) {
  name: take('module.app-insights.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: azureAiServiceLocation
    tags: tags
    enableTelemetry: enableTelemetry
    workspaceResourceId: logAnalyticsWorkspaceResourceId
    retentionInDays: 365
    disableIpMasking: false
  }
}

// ============================================================================
// Module: Networking (WAF — conditional on enablePrivateNetworking)
// ============================================================================

module virtualNetwork './modules/networking/virtual-network.bicep' = if (enablePrivateNetworking) {
  name: take('module.virtual-network.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    addressPrefixes: ['10.0.0.0/8']
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceResourceId
    resourceSuffix: solutionSuffix
  }
}

// ========== Bastion Host — secure access to jumpbox VM ========== //
module bastionHost './modules/networking/bastion-host.bicep' = if (enablePrivateNetworking) {
  name: take('module.bastion-host.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    virtualNetworkResourceId: virtualNetwork!.outputs.resourceId
    publicIPDiagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
  }
}

// ========== WAF: Maintenance Configuration for VM patching ========== //
module maintenanceConfiguration './modules/compute/maintenance-configuration.bicep' = if (enablePrivateNetworking) {
  name: take('module.maintenance-configuration.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// ========== WAF: Data Collection Rules for VM monitoring ========== //
var dataCollectionRulesLocation = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspace!.location
  : (enableMonitoring ? log_analytics!.outputs.location : location)
module windowsVmDataCollectionRules './modules/monitoring/data-collection-rule.bicep' = if (enablePrivateNetworking && enableMonitoring) {
  name: take('module.data-collection-rule.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: dataCollectionRulesLocation
    tags: tags
    enableTelemetry: enableTelemetry
    logAnalyticsWorkspaceResourceId: logAnalyticsWorkspaceResourceId
  }
}

// ========== WAF: Proximity Placement Group for VM ========== //
var virtualMachineAvailabilityZone = 1
module proximityPlacementGroup './modules/compute/proximity-placement-group.bicep' = if (enablePrivateNetworking) {
  name: take('module.proximity-placement-group.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    availabilityZone: virtualMachineAvailabilityZone
    vmSizes: [vmSize]
  }
}

// ========== Jumpbox VM — administration access when private networking is enabled ========== //
// ========== Login is via Microsoft Entra ID through Azure Bastion (not local credentials) ========== //
module virtualMachine './modules/compute/virtual-machine.bicep' = if (enablePrivateNetworking) {
  name: take('module.virtual-machine.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    vmSize: vmSize
    availabilityZone: virtualMachineAvailabilityZone
    adminUsername: vmAdminUsername ?? 'testvmuser'
    adminPassword: vmAdminPassword ?? 'Vm!${uniqueString(subscription().subscriptionId, solutionName)}${guid(subscription().subscriptionId, solutionName, 'vm-admin-password')}'
    subnetResourceId: virtualNetwork!.outputs.administrationSubnetResourceId
    deployingUserPrincipalId: deployingUserPrincipalId
    deployingUserPrincipalType: deployingUserPrincipalType
    roleAssignments: [
      {
        roleDefinitionIdOrName: '1c0163c0-47e6-4577-8991-ea5c82e286e4' // Virtual Machine Administrator Login
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
    ]
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    maintenanceConfigurationResourceId: maintenanceConfiguration!.outputs.resourceId
    proximityPlacementGroupResourceId: proximityPlacementGroup!.outputs.resourceId
    extensionMonitoringAgentConfig: enableMonitoring ? {
      dataCollectionRuleAssociations: [
        {
          dataCollectionRuleResourceId: windowsVmDataCollectionRules!.outputs.resourceId
          name: 'send-${logAnalyticsWorkspaceName}'
        }
      ]
      enabled: true
      tags: tags
    } : null
  }
}

// ========== Private DNS Zones — one per service, linked to VNet ========== //
@batchSize(5)
module privateDnsZoneDeployments './modules/networking/private-dns-zone.bicep' = [
  for (zone, i) in privateDnsZones: if (enablePrivateNetworking) {
    name: take('module.private-dns-zone.${split(zone, '.')[1]}.${solutionName}', 64)
    params: {
      name: zone
      tags: tags
      enableTelemetry: enableTelemetry
      virtualNetworkLinks: [
        {
          name: take('vnetlink-${virtualNetwork!.outputs.name}-${split(zone, '.')[1]}', 80)
          virtualNetworkResourceId: virtualNetwork!.outputs.resourceId
        }
      ]
    }
  }
]

// ============================================================================
// Module: AI Services (conditional — skip if using existing project)
// ============================================================================

// ========== Existing AI Foundry reference (for cross-subscription support when using existing project) ========== //
var aiFoundryResourceGroupName = useExistingAIProject
  ? split(existingFoundryProjectResourceId, '/')[4]
  : resourceGroup().name
var aiFoundrySubscriptionId = useExistingAIProject
  ? split(existingFoundryProjectResourceId, '/')[2]
  : subscription().subscriptionId
var aiFoundryResourceName = useExistingAIProject
  ? split(existingFoundryProjectResourceId, '/')[8]
  : ai_foundry_project!.outputs.name
var aiProjectResourceName = useExistingAIProject
  ? (length(split(existingFoundryProjectResourceId, '/')) > 10 ? split(existingFoundryProjectResourceId, '/')[10] : '')
  : ai_foundry_project!.outputs.projectName

// ========== Reference existing AI Foundry project (identity only) ========== //
module existing_project_setup './modules/ai/existing-project-setup.bicep' = if (useExistingAIProject) {
  name: take('module.existing-project-setup.${solutionName}', 64)
  scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
  params: {
    name: aiFoundryResourceName
    projectName: aiProjectResourceName
  }
}

// ========== Deploy new AI Services account + AI Foundry project (no connections, no deployments) ========== //
module ai_foundry_project './modules/ai/ai-foundry-project.bicep' = if (!useExistingAIProject) {
  name: take('module.ai-foundry-project.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: azureAiServiceLocation
    tags: tags
    enableTelemetry: enableTelemetry
    // Temporarily public — AI Search Knowledge Base needs to call the AI Services model endpoint for answer synthesis.
    publicNetworkAccess: 'Enabled'
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    roleAssignments: [
      {
        roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
      {
        roleDefinitionIdOrName: '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Foundry User
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
    ]
  }
}

// ========== AI outputs (ternary: existing vs new) ========== //
var aiFoundryEndpoint = useExistingAIProject ? existing_project_setup!.outputs.endpoint : ai_foundry_project!.outputs.endpoint
var azureOpenAiCuEndpoint = useExistingAIProject ? existing_project_setup!.outputs.azureOpenAiCuEndpoint : ai_foundry_project!.outputs.azureOpenAiCuEndpoint
var projectEndpoint = useExistingAIProject ? existing_project_setup!.outputs.projectEndpoint : ai_foundry_project!.outputs.projectEndpoint
var aiFoundryName = useExistingAIProject ? existing_project_setup!.outputs.name : ai_foundry_project!.outputs.name
var aiProjectName = useExistingAIProject ? existing_project_setup!.outputs.projectName : ai_foundry_project!.outputs.projectName
var aiFoundryResourceId = useExistingAIProject ? existing_project_setup!.outputs.resourceId : ai_foundry_project!.outputs.resourceId
var aiProjectPrincipalId = useExistingAIProject ? existing_project_setup!.outputs.projectIdentityPrincipalId : ai_foundry_project!.outputs.projectIdentityPrincipalId

// ========== AI Search connection (single call for both existing and new paths) ========== //
module foundry_search_connection './modules/ai/ai-foundry-connection.bicep' = {
  name: take('module.foundry-search-conn.${solutionName}', 64)
  scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
  params: {
    solutionName: solutionSuffix
    aiServicesAccountName: aiFoundryResourceName
    projectName: aiProjectResourceName
    category: 'CognitiveSearch'
    target: ai_search!.outputs.endpoint
    authType: 'AAD'
    metadata: {
      ApiType: 'Azure'
      ResourceId: ai_search!.outputs.resourceId
    }
  }
}

// ========== Model deployments (single loop for both existing and new paths) ========== //
@batchSize(1)
module model_deployments './modules/ai/ai-foundry-model-deployment.bicep' = [for (deployment, i) in aiModelDeployments: {
  name: take('module.model-deployment-${i}.${solutionName}', 64)
  scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
  params: {
    aiServicesAccountName: aiFoundryResourceName
    deploymentName: deployment.name
    modelName: deployment.model
    modelVersion: deployment.version
    raiPolicyName: deployment.raiPolicyName
    skuName: deployment.sku.name
    skuCapacity: deployment.sku.capacity
  }
}]

// // ========== Separate PE for AI Foundry to avoid AccountProvisioningStateInvalid race condition ========== //
// module aifoundry_private_endpoint './modules/networking/private-endpoint.bicep' = if (!useExistingAIProject && enablePrivateNetworking) {
//   name: take('module.pe-ai-foundry.${solutionName}', 64)
//   dependsOn: [privateDnsZoneDeployments]
//   params: {
//     name: 'pep-aif-${solutionSuffix}'
//     location: location
//     tags: tags
//     subnetResourceId: virtualNetwork!.outputs.backendSubnetResourceId
//     privateLinkServiceConnections: [
//       {
//         name: 'pep-aif-${solutionSuffix}'
//         properties: {
//           privateLinkServiceId: ai_foundry_project!.outputs.resourceId
//           groupIds: ['account']
//         }
//       }
//     ]
//     privateDnsZoneGroup: {
//       privateDnsZoneGroupConfigs: [
//         {
//           name: 'ai-services-dns-zone-cognitiveservices'
//           privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
//         }
//         {
//           name: 'ai-services-dns-zone-openai'
//           privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.openAI]!.outputs.resourceId
//         }
//         {
//           name: 'ai-services-dns-zone-aiservices'
//           privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.aiServices]!.outputs.resourceId
//         }
//       ]
//     }
//   }
// }

// ========== AI Search service (called by Foundry connection module, so deployed after the project) ========== //
module ai_search './modules/ai/ai-search.bicep' = {
  name: take('module.ai-search.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: searchServiceLocation
    tags: tags
    enableTelemetry: enableTelemetry
    // Temporarily public — Foundry Agent runtime runs outside the VNET and cannot resolve private DNS for AI Search.
    publicNetworkAccess: 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    roleAssignments: [
      {
        roleDefinitionIdOrName: '8ebe5a00-799e-43f5-93ac-243d3dce84a7' // Search Index Data Contributor
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
      {
        roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0' // Search Service Contributor
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
    ]
    // Temporarily no private endpoint — Foundry Agent cannot resolve private DNS for AI Search.
    privateEndpoints: []
  }
}

// ============================================================================
// Module: Data 
// ============================================================================

module storage_account './modules/data/storage-account.bicep' = {
  name: take('module.storage-account.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    containers: [
      { name: 'data', publicAccess: 'None' }
    ]
    roleAssignments: [
      {
        roleDefinitionIdOrName: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
    ]
    enablePrivateNetworking: enablePrivateNetworking
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.storageBlob]!.outputs.resourceId
    ] : []
  }
}

// ========== Cosmos DB module with single container for conversation history, partitioned by user ID ========== //
module cosmosDBModule './modules/data/cosmos-db-nosql.bicep' = {
  name: take('module.cosmos-db-nosql.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    databaseName: 'db_conversation_history'
    containers: [
      { name: 'conversations', partitionKeyPath: '/userId' }
    ]
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    zoneRedundant: enableRedundancy
    enableAutomaticFailover: enableRedundancy
    haLocation: cosmosDbHaLocation
    enablePrivateNetworking: enablePrivateNetworking
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.cosmosDB]!.outputs.resourceId
    ] : []
  }
}

// ========== SQL Database module ========== //
module sqlDBModule './modules/data/sql-database.bicep' = {
  name: take('module.sql-db.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    name: 'sql-${solutionSuffix}'
    databaseName: 'sqldb-${solutionSuffix}'
    location: secondaryLocation
    tags: tags
    enableTelemetry: enableTelemetry
    deployerPrincipalId: deployingUserPrincipalId
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    enablePrivateNetworking: enablePrivateNetworking
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.sqlServer]!.outputs.resourceId
    ] : []
  }
}

// ============================================================================
// Module: Compute
// ============================================================================

module hostingplan './modules/compute/app-service-plan.bicep' = {
  name: take('module.app-service-plan.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    skuName: (enableScalability || enableRedundancy) ? 'P1v4' : appServicePlanSku
    skuCapacity: enableScalability ? 3 : 1
    zoneRedundant: enableRedundancy
    diagnosticSettings: monitoringDiagnosticSettings
  }
}

var backendApiImageName = 'DOCKER|${backendContainerRegistryHostname}/${backendContainerImageName}:${backendContainerImageTag}'
var frontendImageName = 'DOCKER|${frontendContainerRegistryHostname}/${frontendContainerImageName}:${frontendContainerImageTag}'
var reactAppLayoutConfig = '''{
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

// ========== Backend Deployment ========== //
module backend_docker './modules/compute/app-service.bicep' = {
  name: take('module.app-service-backend.${solutionName}', 64)
  params: {
    solutionName: 'api-${solutionSuffix}'
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    serverFarmResourceId: hostingplan!.outputs.resourceId
    linuxFxVersion: backendApiImageName
    virtualNetworkSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.webserverfarmSubnetResourceId : ''
    publicNetworkAccess: 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    appSettings: {
      AGENT_NAME_CONVERSATION: ''
      AGENT_NAME_TITLE: ''
      APPLICATIONINSIGHTS_CONNECTION_STRING: enableMonitoring ? app_insights!.outputs.connectionString : ''
      APP_ENV: 'Prod'
      API_APP_NAME: 'api-${solutionSuffix}'
      AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
      AZURE_AI_AGENT_ENDPOINT: projectEndpoint
      AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
      AZURE_AI_SEARCH_CONNECTION_NAME: foundry_search_connection.outputs.connectionName
      AZURE_AI_SEARCH_ENDPOINT: ai_search.outputs.endpoint
      AZURE_AI_SEARCH_INDEX: 'call_transcripts_index'
      AZURE_BASIC_LOGGING_LEVEL: 'INFO'
      AZURE_COSMOSDB_ACCOUNT: cosmosDBModule!.outputs.name
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: cosmosDBModule!.outputs.containerName
      AZURE_COSMOSDB_DATABASE: cosmosDBModule!.outputs.databaseName
      AZURE_COSMOSDB_ENABLE_FEEDBACK: 'True'
      AZURE_LOGGING_PACKAGES: ''
      AZURE_PACKAGE_LOGGING_LEVEL: 'WARNING'
      DISPLAY_CHART_DEFAULT: 'False'
      DUMMY_TEST: 'True'
      REACT_APP_LAYOUT_CONFIG: reactAppLayoutConfig
      SOLUTION_NAME: solutionSuffix
      SQLDB_DATABASE: sqlDBModule!.outputs.databaseName
      SQLDB_SERVER: sqlDBModule!.outputs.serverFqdn
      USE_AI_PROJECT_CLIENT: 'True'
      USE_CHAT_HISTORY_ENABLED: 'True'
    }
  }
}

// Frontend
module frontend_docker './modules/compute/app-service.bicep' = {
  name: take('module.app-service-frontend.${solutionName}', 64)
  params: {
    solutionName: 'app-${solutionSuffix}'
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    serverFarmResourceId: hostingplan!.outputs.resourceId
    linuxFxVersion: frontendImageName
    virtualNetworkSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.webserverfarmSubnetResourceId : ''
    publicNetworkAccess: 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    appSettings: {
      APPLICATIONINSIGHTS_CONNECTION_STRING: enableMonitoring ? app_insights!.outputs.connectionString : ''
      APP_API_BASE_URL: enablePrivateNetworking ? '' : 'https://api-${solutionSuffix}.azurewebsites.net'
      BACKEND_API_HOST: enablePrivateNetworking ? 'api-${solutionSuffix}.azurewebsites.net' : ''
    }
  }
}

// ============================================================================
// Module: Role Assignments (centralized)
// ============================================================================

module role_assignments './modules/identity/role-assignments.bicep' = {
  name: take('module.role-assignments.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    useExistingAIProject: useExistingAIProject
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    aiFoundryResourceId: !useExistingAIProject ? aiFoundryResourceId : ''
    aiSearchResourceId: ai_search.outputs.resourceId
    storageAccountResourceId: storage_account.outputs.resourceId
    aiProjectPrincipalId: aiProjectPrincipalId
    aiSearchPrincipalId: ai_search.outputs.identityPrincipalId
    backendAppServicePrincipalId: backend_docker!.outputs.identityPrincipalId
    cosmosDbAccountName: cosmosDBModule!.outputs.name
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Contains Azure Container Registry name.')
output ACR_NAME string = containerRegistryName

@description('Azure AI Foundry resource ID for role assignments')
output AI_FOUNDRY_RESOURCE_ID string = aiFoundryResourceId

@description('Contains Conversation Agent name.')
output AGENT_NAME_CONVERSATION string = ''

@description('Contains Title Agent name.')
output AGENT_NAME_TITLE string = ''

@description('Backend API App Service name')
output API_APP_NAME string = backend_docker!.outputs.name

@description('API App Service principal ID')
output API_APP_PRINCIPAL_ID string = backend_docker!.outputs.identityPrincipalId

@description('Contains API application URL.')
output API_APP_URL string = backend_docker!.outputs.appUrl

@description('Contains Application Insights connection string.')
output APPLICATIONINSIGHTS_CONNECTION_STRING string = app_insights.outputs.connectionString

@description('Contains Application Insights Instrumentation Key.')
output APPINSIGHTS_INSTRUMENTATIONKEY string = app_insights.outputs.instrumentationKey

@description('Contains Azure AI Agent API Version.')
output AZURE_AI_AGENT_API_VERSION string = azureAiAgentApiVersion

@description('Azure AI Agent service endpoint URL')
output AZURE_AI_AGENT_ENDPOINT string = projectEndpoint

@description('Contains Azure AI Foundry service name.')
output AZURE_AI_FOUNDRY_NAME string = aiFoundryName

@description('Azure AI Foundry project name')
output AZURE_AI_PROJECT_NAME string = aiProjectName

@description('AI Foundry connection name for Azure AI Search')
output AZURE_AI_SEARCH_CONNECTION_NAME string = foundry_search_connection.outputs.connectionName

@description('Azure AI Search service endpoint URL')
output AZURE_AI_SEARCH_ENDPOINT string = ai_search.outputs.endpoint

@description('Azure AI Search index name for document search')
output AZURE_AI_SEARCH_INDEX string = 'call_transcripts_index'

@description('Azure AI Search service resource name')
output AZURE_AI_SEARCH_NAME string = ai_search.outputs.name

@description('Cosmos DB account name for conversation history storage')
output AZURE_COSMOSDB_ACCOUNT string = cosmosDBModule!.outputs.name

@description('Cosmos DB container name for storing conversations')
output AZURE_COSMOSDB_CONVERSATIONS_CONTAINER string = 'conversations'

@description('Cosmos DB database name for conversation history')
output AZURE_COSMOSDB_DATABASE string = 'db_conversation_history'

@description('Contains Azure Cosmos DB feedback enablement setting.')
output AZURE_COSMOSDB_ENABLE_FEEDBACK string = 'True'

@description('Contains Content Understanding API version.')
output AZURE_CONTENT_UNDERSTANDING_API_VERSION string = azureContentUnderstandingApiVersion

@description('Contains Azure OpenAI embedding model capacity.')
output AZURE_ENV_EMBEDDING_DEPLOYMENT_CAPACITY int = embeddingDeploymentCapacity

@description('Contains Azure OpenAI embedding model name.')
output AZURE_ENV_EMBEDDING_MODEL_NAME string = embeddingModel

@description('Contains Azure OpenAI deployment model capacity.')
output AZURE_ENV_GPT_MODEL_CAPACITY int = gptDeploymentCapacity

@description('GPT model deployment name (e.g., gpt-4o-mini)')
output AZURE_ENV_GPT_MODEL_NAME string = gptModelName

@description('Contains Azure environment image tag.')
output AZURE_ENV_IMAGE_TAG string = backendContainerImageTag

@description('Contains Azure OpenAI model deployment type.')
output AZURE_ENV_MODEL_DEPLOYMENT_TYPE string = deploymentType

@description('Model deployment name used by Azure AI Agent')
output AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME string = gptModelName

@description('Azure OpenAI service endpoint URL')
output AZURE_OPENAI_ENDPOINT string = aiFoundryEndpoint

@description('Azure OpenAI Content Understanding endpoint URL.')
output AZURE_OPENAI_CU_ENDPOINT string = azureOpenAiCuEndpoint

@description('Contains Azure OpenAI resource name.')
output AZURE_OPENAI_RESOURCE string = aiFoundryName

@description('Client ID of the backend API user-assigned managed identity.')
output BACKEND_USER_MID string = ''

@description('Display name of the backend API user-assigned managed identity.')
output BACKEND_USER_MID_NAME string = ''

@description('WAF deployment type.')
output DEPLOYMENT_TYPE string = enablePrivateNetworking ? 'WAF' : 'Non-WAF'

@description('Contains default chart display setting.')
output DISPLAY_CHART_DEFAULT string = 'False'

@description('Contains React app layout configuration.')
output REACT_APP_LAYOUT_CONFIG string = reactAppLayoutConfig

@description('Contains Resource Group Location.')
output RESOURCE_GROUP_LOCATION string = location

@description('Name of the deployed resource group')
output RESOURCE_GROUP_NAME string = resourceGroup().name

@description('Contains SQL database name.')
output SQLDB_DATABASE string = sqlDBModule!.outputs.databaseName

@description('Contains SQL server name.')
output SQLDB_SERVER string = sqlDBModule!.outputs.serverFqdn

@description('Solution suffix used for naming resources')
output SOLUTION_NAME string = solutionSuffix

@description('Name of the Storage Account.')
output STORAGE_ACCOUNT_NAME string = storage_account.outputs.name

@description('Name of the Storage Container.')
output STORAGE_CONTAINER_NAME string = 'data'

@description('Contains AI project client usage setting.')
output USE_AI_PROJECT_CLIENT string = 'False'

@description('Industry Use Case.')
output USE_CASE string = usecase

@description('Flag indicating whether chat history storage is enabled')
output USE_CHAT_HISTORY_ENABLED string = useChatHistoryEnabledSetting

@description('Frontend web application URL')
output WEB_APP_URL string = frontend_docker!.outputs.appUrl
