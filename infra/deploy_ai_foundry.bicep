// Creates Azure dependent resources for Azure AI studio
param solutionName string
param solutionLocation string
param keyVaultName string
param cuLocation string
param deploymentType string
param gptModelName string
param azureOpenAIApiVersion string
param gptDeploymentCapacity int
param embeddingModel string
param embeddingDeploymentCapacity int
param managedIdentityObjectId string
var abbrs = loadJsonContent('./abbreviations.json')
// var storageName = '${solutionName}hubstorage'
// var storageSkuName = 'Standard_LRS'
// var aiServicesName = '${solutionName}-aiservices'
// var aiServicesName_cu = '${solutionName}-aiservices-cu'
// var location_cu = cuLocation
// // var aiServicesName_m = '${solutionName}-aiservices_m'
// // var location_m = solutionLocation
// var workspaceName = '${solutionName}-workspace'
// var applicationInsightsName = '${solutionName}-appinsights'
// var containerRegistryName = '${solutionName}acr'
// var keyvaultName = '${solutionName}-kv'
// var location = solutionLocation //'eastus2'
// var aiHubName = '${solutionName}-aihub'
// var aiHubFriendlyName = aiHubName
// var aiHubDescription = 'AI Hub for KM template'
// var aiProjectName = '${solutionName}-aiproject'
// var aiProjectFriendlyName = aiProjectName
// var aiSearchName = '${solutionName}-search'

// var containerRegistryNameCleaned = replace(containerRegistryName, '-', '')
var storageName = '${solutionName}hubstorage'
var storageSkuName = 'Standard_LRS'
var aiServicesName = '${abbrs.ai.aiServices}${solutionName}'
var aiServicesName_cu = '${abbrs.ai.aiServices}${solutionName}-cu'
var location_cu = cuLocation
// var aiServicesName_m = '${solutionName}-aiservices_m'
// var location_m = solutionLocation
var workspaceName = '${abbrs.managementGovernance.logAnalyticsWorkspace}${solutionName}'
var applicationInsightsName = '${abbrs.managementGovernance.applicationInsights}${solutionName}'
var containerRegistryName = '${abbrs.containers.containerRegistry}${solutionName}'
var keyvaultName = '${abbrs.security.keyVault}${solutionName}'
var location = solutionLocation //'eastus2'
var aiHubName = '${abbrs.ai.aiHub}${solutionName}'
var aiHubFriendlyName = aiHubName
var aiHubDescription = 'AI Hub for KM template'
var aiProjectName = '${abbrs.ai.aiHubProject}${solutionName}'
var aiProjectFriendlyName = aiProjectName
var aiSearchName = '${abbrs.ai.aiSearch}${solutionName}'

var aiModelDeployments = [
  {
    name: gptModelName
    model: gptModelName
    sku: {
      name: deploymentType
      capacity: gptDeploymentCapacity
    }
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

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: keyVaultName
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
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
    WorkspaceResourceId: logAnalytics.id
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

// resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' = {
//   name: keyvaultName
//   location: solutionLocation
//   properties: {
//     createMode: 'default'
//     accessPolicies: [
//       {        
//         objectId: managedIdentityObjectId        
//         permissions: {
//           certificates: [
//             'all'
//           ]
//           keys: [
//             'all'
//           ]
//           secrets: [
//             'all'
//           ]
//           storage: [
//             'all'
//           ]
//         }
//         tenantId: subscription().tenantId
//       }
//     ]
//     enabledForDeployment: true
//     enabledForDiskEncryption: true
//     enabledForTemplateDeployment: true
//     enableSoftDelete: false
//     enableRbacAuthorization: true
//     enablePurgeProtection: true
//     publicNetworkAccess: 'enabled'
//     // networkAcls: {
//     //   bypass: 'AzureServices'
//     //   defaultAction: 'Deny'
//     // }
//     sku: {
//       family: 'A'
//       name: 'standard'
//     }
//     softDeleteRetentionInDays: 7
//     tenantId: subscription().tenantId
//   }
// }

// @description('This is the built-in Key Vault Administrator role.')
// resource kvAdminRole 'Microsoft.Authorization/roleDefinitions@2018-01-01-preview' existing = {
//   scope: resourceGroup()
//   name: '00482a5a-887f-4fb3-b363-3b7fe8e74483'
// }

// resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
//   name: guid(resourceGroup().id, managedIdentityObjectId, kvAdminRole.id)
//   properties: {
//     principalId: managedIdentityObjectId
//     roleDefinitionId:kvAdminRole.id
//     principalType: 'ServicePrincipal' 
//   }
// }

var storageNameCleaned = replace(storageName, '-', '')

resource aiServices 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: aiServicesName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  properties: {
    customSubDomainName: aiServicesName
  }
}

// resource aiServices_m 'Microsoft.CognitiveServices/accounts@2021-10-01' = {
//   name: aiServicesName //aiServicesName_m
//   location: location_m
//   sku: {
//     name: 'S0'
//   }
//   kind: 'AIServices'
//   properties: {
//     apiProperties: {
//       statisticsEnabled: false
//     }
//   }
// }

resource aiServices_CU 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: aiServicesName_cu
  location: location_cu
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  properties: {
    customSubDomainName: aiServicesName_cu
  }
}

@batchSize(1)
resource aiServicesDeployments 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = [for aiModeldeployment in aiModelDeployments: {
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

resource aiSearch 'Microsoft.Search/searchServices@2023-11-01' = {
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

// resource storageAccounts_default 'Microsoft.Storage/storageAccounts/blobServices@2022-09-01' = {
//   parent: storage
//   name: 'default'
//   properties: {
//     cors: {
//       corsRules: []
//     }
//     deleteRetentionPolicy: {
//       allowPermanentDelete: false
//       enabled: false
//     }
//   }
// }


// resource storageAccounts_default_data 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
//   parent: storageAccounts_default
//   name: 'data'
//   properties: {
//     defaultEncryptionScope: '$account-encryption-key'
//     denyEncryptionScopeOverride: false
//     publicAccess: 'None'
//   }
// }

// resource storageAccounts_default_input 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
//   parent: storageAccounts_default
//   name: 'graphrag'
//   properties: {
//     defaultEncryptionScope: '$account-encryption-key'
//     denyEncryptionScopeOverride: false
//     publicAccess: 'None'
//   }
// }

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

resource aiHub 'Microsoft.MachineLearningServices/workspaces@2023-08-01-preview' = {
  name: aiHubName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    // organization
    friendlyName: aiHubFriendlyName
    description: aiHubDescription

    // dependent resources
    keyVault: keyVault.id
    storageAccount: storage.id
    applicationInsights: applicationInsights.id
    containerRegistry: containerRegistry.id
  }
  kind: 'hub'

  resource aiServicesConnection 'connections@2024-07-01-preview' = {
    name: '${aiHubName}-connection-AzureOpenAI'
    properties: {
      category: 'AIServices'
      target: aiServices.properties.endpoint
      authType: 'ApiKey'
      isSharedToAll: true
      credentials: {
        key: aiServices.listKeys().key1
      }
      metadata: {
        ApiType: 'Azure'
        ResourceId: aiServices.id
      }
    }
    dependsOn: [
      aiServicesDeployments,aiSearch
    ]
  }
  
  resource aiSearchConnection 'connections@2024-07-01-preview' = {
    name: '${aiHubName}-connection-AzureAISearch'
    properties: {
      category: 'CognitiveSearch'
      target: 'https://${aiSearch.name}.search.windows.net'
      authType: 'ApiKey'
      isSharedToAll: true
      credentials: {
        key: aiSearch.listAdminKeys().primaryKey
      }
      metadata: {
        type:'azure_ai_search'
        ApiType: 'Azure'
        ResourceId: aiSearch.id
        ApiVersion:'2024-05-01-preview'
        DeploymentApiVersion:'2023-11-01'
      }
    }
  }
  dependsOn: [
    aiServicesDeployments,aiSearch
  ]
}

resource aiHubProject 'Microsoft.MachineLearningServices/workspaces@2024-01-01-preview' = {
  name: aiProjectName
  location: location
  kind: 'Project'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: aiProjectFriendlyName
    hubResourceId: aiHub.id
  }
}

// var phiModelRegions = ['East US', 'East US 2', 'North Central US', 'South Central US', 'Sweden Central', 'West US', 'West US 3', 'eastus','eastus2','northcentralus','southcentralus','swedencentral','westus','westus3']
  
// var isInPhiList = contains(phiModelRegions, location)

// var serverlessModelName = 'Phi-4' //'Phi-3-medium-4k-instruct'
// var phiserverlessName = '${solutionName}-${serverlessModelName}'
// resource phiserverless 'Microsoft.MachineLearningServices/workspaces/serverlessEndpoints@2024-10-01' = if (isInPhiList) {
//   parent: aiHubProject
//   location: location
//   name: phiserverlessName
//   properties: {
//     authMode: 'Key'
//     contentSafety: {
//       contentSafetyStatus: 'Enabled'
//     }
//     modelSettings: {
//       modelId: 'azureml://registries/azureml/models/${serverlessModelName}'
//     }
//   }
//   sku: {
//     name: 'Consumption'
//     tier: 'Free'
//   }
// }

resource tenantIdEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'TENANT-ID'
  properties: {
    value: subscription().tenantId
  }
}

// resource adlsAccountNameEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
//   parent: keyVault
//   name: 'ADLS-ACCOUNT-NAME'
//   properties: {
//     value: storageName
//   }
// }

// resource adlsAccountContainerEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
//   parent: keyVault
//   name: 'ADLS-ACCOUNT-CONTAINER'
//   properties: {
//     value: 'data'
//   }
// }

// resource adlsAccountKeyEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
//   parent: keyVault
//   name: 'ADLS-ACCOUNT-KEY'
//   properties: {
//     value: storage.listKeys().keys[0].value
//   }
// }

resource azureOpenAIInferenceEndpoint 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-OPENAI-INFERENCE-ENDPOINT'
  properties: {
    // value: phiserverless != null ? phiserverless.properties.inferenceEndpoint.uri : ''
    // value: phiserverless.properties.inferenceEndpoint.uri
    value:''
  }
}

resource azureOpenAIInferenceKey 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-OPENAI-INFERENCE-KEY'
  properties: {
    //value: phiserverless != null ? listKeys(phiserverless.id, '2024-10-01').primaryKey : ''
    // listKeys(phiserverless.id, '2024-10-01').primaryKey
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
    value: aiServices.properties.endpoint //aiServices_m.properties.endpoint
  }
}

resource azureAIProjectConnectionStringEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-AI-PROJECT-CONN-STRING'
  properties: {
    value: '${split(aiHubProject.properties.discoveryUrl, '/')[2]};${subscription().subscriptionId};${resourceGroup().name};${aiHubProject.name}'
  }
}

resource azureOpenAICUEndpointEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'AZURE-OPENAI-CU-ENDPOINT'
  properties: {
    value: aiServices_CU.properties.endpoint
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

output aiServicesTarget string = aiServices.properties.endpoint //aiServices_m.properties.endpoint
output aiServicesName string = aiServicesName //aiServicesName_m
output aiServicesId string = aiServices.id //aiServices_m.id

//output aiInfereceEndpoint string = phiserverless.properties.inferenceEndpoint.uri

output aiSearchName string = aiSearchName
output aiSearchId string = aiSearch.id
output aiSearchTarget string = 'https://${aiSearch.name}.search.windows.net'
output aiSearchService string = aiSearch.name
output aiProjectName string = aiHubProject.name

output applicationInsightsId string = applicationInsights.id
output logAnalyticsWorkspaceResourceName string = logAnalytics.name
output storageAccountName string = storageNameCleaned

output azureOpenAIKeyName string = azureOpenAIApiKeyEntry.name

output azureProjectConnString string = '${split(aiHubProject.properties.discoveryUrl, '/')[2]};${subscription().subscriptionId};${resourceGroup().name};${aiHubProject.name}'
output azureProjectName string = aiHubProject.name
output applicationInsightsConnectionString string = applicationInsights.properties.ConnectionString
