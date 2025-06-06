// Creates Azure dependent resources for Azure AI studio
param solutionName string
param solutionLocation string
param keyVaultName string
param cuLocation string
param deploymentType string
param gptModelName string
param gptModelVersion string
param azureOpenAIApiVersion string
param gptDeploymentCapacity int
param embeddingModel string
param embeddingDeploymentCapacity int
param managedIdentityObjectId string
param existingLogAnalyticsWorkspaceId string = ''

var abbrs = loadJsonContent('./abbreviations.json')
var storageName = '${solutionName}hubstorage'
var storageSkuName = 'Standard_LRS'
var aiServicesName = '${abbrs.ai.aiServices}${solutionName}'
var aiServicesName_cu = '${abbrs.ai.aiServices}${solutionName}-cu'
var location_cu = cuLocation
var workspaceName = '${abbrs.managementGovernance.logAnalyticsWorkspace}${solutionName}'
var applicationInsightsName = '${abbrs.managementGovernance.applicationInsights}${solutionName}'
var containerRegistryName = '${abbrs.containers.containerRegistry}${solutionName}'
var keyvaultName = '${abbrs.security.keyVault}${solutionName}'
var location = solutionLocation //'eastus2'
var aiProjectName = '${abbrs.ai.aiHubProject}${solutionName}'
var aiSearchName = '${abbrs.ai.aiSearch}${solutionName}'

var aiModelDeployments = [
  {
    name: gptModelName
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
    model: embeddingModel
    sku: {
      name: 'Standard'
      capacity: embeddingDeploymentCapacity
    }
    raiPolicyName: 'Microsoft.Default'
  }
]

var containerRegistryNameCleaned = replace(containerRegistryName, '-', '')

var useExisting = !empty(existingLogAnalyticsWorkspaceId)
var existingLawSubscription = useExisting ? split(existingLogAnalyticsWorkspaceId, '/')[2] : ''
var existingLawResourceGroup = useExisting ? split(existingLogAnalyticsWorkspaceId, '/')[4] : ''
var existingLawName = useExisting ? split(existingLogAnalyticsWorkspaceId, '/')[8] : ''

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: keyVaultName
}

resource existingLogAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = if (useExisting) {
  name: existingLawName
  scope: resourceGroup(existingLawSubscription ,existingLawResourceGroup)
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (!useExisting){
  name: workspaceName
  location: location
  tags: {}
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Disabled'
    WorkspaceResourceId: useExisting ? existingLogAnalyticsWorkspace.id : logAnalytics.id
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2021-09-01' = {
  name: containerRegistryNameCleaned
  location: location
  sku: {
    name: 'Premium'
  }
  properties: {
    adminUserEnabled: false
    dataEndpointEnabled: false
    networkRuleBypassOptions: 'AzureServices'
    networkRuleSet: {
      defaultAction: 'Deny'
    }
    policies: {
      quarantinePolicy: {
        status: 'disabled'
      }
      retentionPolicy: {
        status: 'enabled'
        days: 7
      }
      trustPolicy: {
        status: 'disabled'
        type: 'Notary'
      }
    }
    publicNetworkAccess: 'Disabled'
    zoneRedundancy: 'Disabled'
  }
}

var storageNameCleaned = replace(storageName, '-', '')

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: aiServicesName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: aiServicesName
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false //needs to be false to access keys 
  }
}

resource aiServices_CU 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: aiServicesName_cu
  location: location_cu
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: aiServicesName_cu
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false //needs to be false to access keys 
  }
}

@batchSize(1)
resource aiServicesDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = [for aiModeldeployment in aiModelDeployments: {
  parent: aiServices //aiServices_m
  name: aiModeldeployment.name
  properties: {
    model: {
      format: 'OpenAI'
      name: aiModeldeployment.model
    }
    raiPolicyName: aiModeldeployment.raiPolicyName
  }
  sku:{
    name: aiModeldeployment.sku.name
    capacity: aiModeldeployment.sku.capacity
  }
}]

resource aiSearch 'Microsoft.Search/searchServices@2024-06-01-preview' = {
    name: aiSearchName
    location: solutionLocation
    sku: {
      name: 'basic'
    }
    properties: {
      replicaCount: 1
      partitionCount: 1
      hostingMode: 'default'
      publicNetworkAccess: 'enabled'
      networkRuleSet: {
        ipRules: []
      }
      encryptionWithCmk: {
        enforcement: 'Unspecified'
      }
      disableLocalAuth: false
      authOptions: {
        apiKeyOnly: {}
      }
      semanticSearch: 'free'
    }
  }

resource storage 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: storageNameCleaned
  location: location
  sku: {
    name: storageSkuName
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowCrossTenantReplication: false
    allowSharedKeyAccess: false
    encryption: {
      keySource: 'Microsoft.Storage'
      requireInfrastructureEncryption: false
      services: {
        blob: {
          enabled: true
          keyType: 'Account'
        }
        file: {
          enabled: true
          keyType: 'Account'
        }
        queue: {
          enabled: true
          keyType: 'Service'
        }
        table: {
          enabled: true
          keyType: 'Service'
        }
      }
    }
    isHnsEnabled: false
    isNfsV3Enabled: false
    keyPolicy: {
      keyExpirationPeriodInDays: 7
    }
    largeFileSharesState: 'Disabled'
    minimumTlsVersion: 'TLS1_2'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
    supportsHttpsTrafficOnly: true
  }
}

@description('This is the built-in Storage Blob Data Contributor.')
resource blobDataContributor 'Microsoft.Authorization/roleDefinitions@2018-01-01-preview' existing = {
  scope: resourceGroup()
  name: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
}

resource storageroleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, managedIdentityObjectId, blobDataContributor.id)
  properties: {
    principalId: managedIdentityObjectId
    roleDefinitionId:blobDataContributor.id
    principalType: 'ServicePrincipal' 
  }
}

resource storageroleAiServiceAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, aiServices.id, blobDataContributor.id)
  properties: {
    principalId: aiServices.identity.principalId
    roleDefinitionId: blobDataContributor.id
    principalType: 'ServicePrincipal' 
  }
}

resource cognitiveServicesUserRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: aiServices_CU
  name: 'a97b65f3-24c7-4388-baec-2e87135dc908'
}

resource cognitiveServicesUserAccessProj 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, managedIdentityObjectId, cognitiveServicesUserRoleDefinition.id)
  properties: {
    principalId: managedIdentityObjectId
    roleDefinitionId: cognitiveServicesUserRoleDefinition.id
    principalType: 'ServicePrincipal' 
  }
}

resource cognitiveServicesUserAiServiceAccessProj 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, aiServices.id, cognitiveServicesUserRoleDefinition.id)
  properties: {
    principalId: aiServices.identity.principalId
    roleDefinitionId: cognitiveServicesUserRoleDefinition.id
    principalType: 'ServicePrincipal' 
  }
}


resource aiDeveloperRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: aiServices_CU
  name: '64702f94-c441-49e6-a78b-ef80e0188fee'
}

resource aiDeveloperAccessProj 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, managedIdentityObjectId, aiDeveloperRoleDefinition.id)
  properties: {
    principalId: managedIdentityObjectId
    roleDefinitionId: aiDeveloperRoleDefinition.id
    principalType: 'ServicePrincipal' 
  }
}

resource aiDeveloperAiServiceAccessProj 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, aiServices.id, aiDeveloperRoleDefinition.id)
  properties: {
    principalId: aiServices.identity.principalId
    roleDefinitionId: aiDeveloperRoleDefinition.id
    principalType: 'ServicePrincipal' 
  }
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiServices
  name: aiProjectName
  location: solutionLocation
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

resource project_connection_azureai_search 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  name: 'myVectorStoreProjectConnectionName'
  parent: aiProject
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${aiSearchName}.search.windows.net'
    authType: 'AAD'
    //useWorkspaceManagedIdentity: false
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: aiSearch.id
      location: aiSearch.location
    }
  }
}

resource project_connection_azure_storage 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  name: 'myStorageProjectConnectionName'
  parent: aiProject
  properties: {
    category: 'AzureBlob'
    target: storage.properties.primaryEndpoints.blob
    authType: 'AAD'
    metadata: {
      ApiType: 'Azure'
      ResourceId: storage.id
      location: storage.location
      containerName: 'ai-container'
      accountName: storage.name
    }
  }
}

resource tenantIdEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'TENANT-ID'
  properties: {
    value: subscription().tenantId
  }
}

resource azureOpenAIInferenceEndpoint 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-OPENAI-INFERENCE-ENDPOINT'
  properties: {
    value:''
  }
}

resource azureOpenAIInferenceKey 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-OPENAI-INFERENCE-KEY'
  properties: {
    value:''
  }
}

resource azureOpenAIApiKeyEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-OPENAI-KEY'
  properties: {
    value: aiServices.listKeys().key1 //aiServices_m.listKeys().key1
  }
}

resource azureOpenAIDeploymentModel 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-OPEN-AI-DEPLOYMENT-MODEL'
  properties: {
    value: gptModelName
  }
}

resource azureOpenAIApiVersionEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-OPENAI-PREVIEW-API-VERSION'
  properties: {
    value: azureOpenAIApiVersion  //'2024-02-15-preview'
  }
}

resource azureOpenAIEndpointEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-OPENAI-ENDPOINT'
  properties: {
    value: aiServices.properties.endpoints['OpenAI Language Model Instance API'] //aiServices_m.properties.endpoint
  }
}

resource azureAIProjectConnectionStringEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-AI-PROJECT-CONN-STRING'
  properties: {
    value: '${aiProjectName};${subscription().subscriptionId};${resourceGroup().name};${aiProject.name}'
  }
}

resource azureOpenAICUEndpointEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-OPENAI-CU-ENDPOINT'
  properties: {
    value: aiServices_CU.properties.endpoints['OpenAI Language Model Instance API']
  }
}

resource azureOpenAICUApiKeyEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-OPENAI-CU-KEY'
  properties: {
    value: aiServices_CU.listKeys().key1
  }
}

resource azureOpenAICUApiVersionEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-OPENAI-CU-VERSION'
  properties: {
    value: '?api-version=2024-12-01-preview'
  }
}

resource azureSearchAdminKeyEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-SEARCH-KEY'
  properties: {
    value: aiSearch.listAdminKeys().primaryKey
  }
}

resource azureSearchServiceEndpointEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-SEARCH-ENDPOINT'
  properties: {
    value: 'https://${aiSearch.name}.search.windows.net'
  }
}

resource azureSearchServiceEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-SEARCH-SERVICE'
  properties: {
    value: aiSearch.name
  }
}

resource azureSearchIndexEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-SEARCH-INDEX'
  properties: {
    value: 'transcripts_index'
  }
}

resource cogServiceEndpointEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'COG-SERVICES-ENDPOINT'
  properties: {
    value: aiServices.properties.endpoint
  }
}

resource cogServiceKeyEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'COG-SERVICES-KEY'
  properties: {
    value: aiServices.listKeys().key1
  }
}

resource cogServiceNameEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'COG-SERVICES-NAME'
  properties: {
    value: aiServicesName
  }
}

resource azureSubscriptionIdEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-SUBSCRIPTION-ID'
  properties: {
    value: subscription().subscriptionId
  }
}

resource resourceGroupNameEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-RESOURCE-GROUP'
  properties: {
    value: resourceGroup().name
  }
}

resource azureLocatioEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-LOCATION'
  properties: {
    value: solutionLocation
  }
}

output keyvaultName string = keyvaultName
output keyvaultId string = keyVault.id
output aiServicesTarget string = aiServices.properties.endpoints['OpenAI Language Model Instance API'] //aiServices_m.properties.endpoint
output aiServicesName string = aiServicesName //aiServicesName_m
output aiServicesId string = aiServices.id //aiServices_m.id

output aiSearchName string = aiSearchName
output aiSearchId string = aiSearch.id
output aiSearchTarget string = 'https://${aiSearch.name}.search.windows.net'
output aiSearchService string = aiSearch.name
output aiProjectName string = aiProject.name

output applicationInsightsId string = applicationInsights.id
output logAnalyticsWorkspaceResourceName string = useExisting ? existingLogAnalyticsWorkspace.name : logAnalytics.name
output logAnalyticsWorkspaceResourceGroup string = useExisting ? existingLawResourceGroup : resourceGroup().name
output logAnalyticsWorkspaceSubscription string = useExisting ? existingLawSubscription : subscription().subscriptionId

output storageAccountName string = storageNameCleaned

output azureOpenAIKeyName string = azureOpenAIApiKeyEntry.name

output projectEndpoint string = aiProject.properties.endpoints['AI Foundry API']
output applicationInsightsConnectionString string = applicationInsights.properties.ConnectionString
