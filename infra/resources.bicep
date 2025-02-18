@description('The location used for all deployed resources')
param location string = resourceGroup().location

@description('Tags that will be applied to all resources')
param tags object = {}


param appExists bool
@secure()
param appDefinition object
param kmChartsFunctionExists bool
@secure()
param kmChartsFunctionDefinition object
param kmRagFunctionExists bool
@secure()
param kmRagFunctionDefinition object
param addUserScriptsExists bool
@secure()
param addUserScriptsDefinition object
param fabricScriptsExists bool
@secure()
param fabricScriptsDefinition object
param indexScriptsExists bool
@secure()
param indexScriptsDefinition object

@description('Id of the user or app to assign application roles')
param principalId string

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location)

// Monitor application with Azure Monitor
module monitoring 'br/public:avm/ptn/azd/monitoring:0.1.0' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsName: '${abbrs.insightsComponents}${resourceToken}'
    applicationInsightsDashboardName: '${abbrs.portalDashboards}${resourceToken}'
    location: location
    tags: tags
  }
}

// Container registry
module containerRegistry 'br/public:avm/res/container-registry/registry:0.1.1' = {
  name: 'registry'
  params: {
    name: '${abbrs.containerRegistryRegistries}${resourceToken}'
    location: location
    acrAdminUserEnabled: true
    tags: tags
    publicNetworkAccess: 'Enabled'
    roleAssignments:[
      {
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
      }
      {
        principalId: kmChartsFunctionIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
      }
      {
        principalId: kmRagFunctionIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
      }
      {
        principalId: addUserScriptsIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
      }
      {
        principalId: fabricScriptsIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
      }
      {
        principalId: indexScriptsIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
      }
    ]
  }
}

// Container apps environment
module containerAppsEnvironment 'br/public:avm/res/app/managed-environment:0.4.5' = {
  name: 'container-apps-environment'
  params: {
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    name: '${abbrs.appManagedEnvironments}${resourceToken}'
    location: location
    zoneRedundant: false
  }
}

module appIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.2.1' = {
  name: 'appidentity'
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}app-${resourceToken}'
    location: location
  }
}

module appFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'app-fetch-image'
  params: {
    exists: appExists
    name: 'app'
  }
}

var appAppSettingsArray = filter(array(appDefinition.settings), i => i.name != '')
var appSecrets = map(filter(appAppSettingsArray, i => i.?secret != null), i => {
  name: i.name
  value: i.value
  secretRef: i.?secretRef ?? take(replace(replace(toLower(i.name), '_', '-'), '.', '-'), 32)
})
var appEnv = map(filter(appAppSettingsArray, i => i.?secret == null), i => {
  name: i.name
  value: i.value
})

module app 'br/public:avm/res/app/container-app:0.8.0' = {
  name: 'app'
  params: {
    name: 'app'
    ingressTargetPort: 80
    scaleMinReplicas: 1
    scaleMaxReplicas: 10
    secrets: {
      secureList:  union([
      ],
      map(appSecrets, secret => {
        name: secret.secretRef
        value: secret.value
      }))
    }
    containers: [
      {
        image: appFetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        name: 'main'
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: union([
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: monitoring.outputs.applicationInsightsConnectionString
          }
          {
            name: 'AZURE_CLIENT_ID'
            value: appIdentity.outputs.clientId
          }
          {
            name: 'PORT'
            value: '80'
          }
        ],
        appEnv,
        map(appSecrets, secret => {
            name: secret.name
            secretRef: secret.secretRef
        }))
      }
    ]
    managedIdentities:{
      systemAssigned: false
      userAssignedResourceIds: [appIdentity.outputs.resourceId]
    }
    registries:[
      {
        server: containerRegistry.outputs.loginServer
        identity: appIdentity.outputs.resourceId
      }
    ]
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    location: location
    tags: union(tags, { 'azd-service-name': 'app' })
  }
}

module kmChartsFunctionIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.2.1' = {
  name: 'kmChartsFunctionidentity'
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}kmChartsFunction-${resourceToken}'
    location: location
  }
}

module kmChartsFunctionFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'kmChartsFunction-fetch-image'
  params: {
    exists: kmChartsFunctionExists
    name: 'km-charts-function'
  }
}

var kmChartsFunctionAppSettingsArray = filter(array(kmChartsFunctionDefinition.settings), i => i.name != '')
var kmChartsFunctionSecrets = map(filter(kmChartsFunctionAppSettingsArray, i => i.?secret != null), i => {
  name: i.name
  value: i.value
  secretRef: i.?secretRef ?? take(replace(replace(toLower(i.name), '_', '-'), '.', '-'), 32)
})
var kmChartsFunctionEnv = map(filter(kmChartsFunctionAppSettingsArray, i => i.?secret == null), i => {
  name: i.name
  value: i.value
})

module kmChartsFunction 'br/public:avm/res/app/container-app:0.8.0' = {
  name: 'kmChartsFunction'
  params: {
    name: 'km-charts-function'
    ingressTargetPort: 5000
    scaleMinReplicas: 1
    scaleMaxReplicas: 10
    secrets: {
      secureList:  union([
      ],
      map(kmChartsFunctionSecrets, secret => {
        name: secret.secretRef
        value: secret.value
      }))
    }
    containers: [
      {
        image: kmChartsFunctionFetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        name: 'main'
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: union([
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: monitoring.outputs.applicationInsightsConnectionString
          }
          {
            name: 'AZURE_CLIENT_ID'
            value: kmChartsFunctionIdentity.outputs.clientId
          }
          {
            name: 'PORT'
            value: '5000'
          }
        ],
        kmChartsFunctionEnv,
        map(kmChartsFunctionSecrets, secret => {
            name: secret.name
            secretRef: secret.secretRef
        }))
      }
    ]
    managedIdentities:{
      systemAssigned: false
      userAssignedResourceIds: [kmChartsFunctionIdentity.outputs.resourceId]
    }
    registries:[
      {
        server: containerRegistry.outputs.loginServer
        identity: kmChartsFunctionIdentity.outputs.resourceId
      }
    ]
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    location: location
    tags: union(tags, { 'azd-service-name': 'km-charts-function' })
  }
}

module kmRagFunctionIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.2.1' = {
  name: 'kmRagFunctionidentity'
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}kmRagFunction-${resourceToken}'
    location: location
  }
}

module kmRagFunctionFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'kmRagFunction-fetch-image'
  params: {
    exists: kmRagFunctionExists
    name: 'km-rag-function'
  }
}

var kmRagFunctionAppSettingsArray = filter(array(kmRagFunctionDefinition.settings), i => i.name != '')
var kmRagFunctionSecrets = map(filter(kmRagFunctionAppSettingsArray, i => i.?secret != null), i => {
  name: i.name
  value: i.value
  secretRef: i.?secretRef ?? take(replace(replace(toLower(i.name), '_', '-'), '.', '-'), 32)
})
var kmRagFunctionEnv = map(filter(kmRagFunctionAppSettingsArray, i => i.?secret == null), i => {
  name: i.name
  value: i.value
})

module kmRagFunction 'br/public:avm/res/app/container-app:0.8.0' = {
  name: 'kmRagFunction'
  params: {
    name: 'km-rag-function'
    ingressTargetPort: 5000
    scaleMinReplicas: 1
    scaleMaxReplicas: 10
    secrets: {
      secureList:  union([
      ],
      map(kmRagFunctionSecrets, secret => {
        name: secret.secretRef
        value: secret.value
      }))
    }
    containers: [
      {
        image: kmRagFunctionFetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        name: 'main'
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: union([
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: monitoring.outputs.applicationInsightsConnectionString
          }
          {
            name: 'AZURE_CLIENT_ID'
            value: kmRagFunctionIdentity.outputs.clientId
          }
          {
            name: 'PORT'
            value: '5000'
          }
        ],
        kmRagFunctionEnv,
        map(kmRagFunctionSecrets, secret => {
            name: secret.name
            secretRef: secret.secretRef
        }))
      }
    ]
    managedIdentities:{
      systemAssigned: false
      userAssignedResourceIds: [kmRagFunctionIdentity.outputs.resourceId]
    }
    registries:[
      {
        server: containerRegistry.outputs.loginServer
        identity: kmRagFunctionIdentity.outputs.resourceId
      }
    ]
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    location: location
    tags: union(tags, { 'azd-service-name': 'km-rag-function' })
  }
}

module addUserScriptsIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.2.1' = {
  name: 'addUserScriptsidentity'
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}addUserScripts-${resourceToken}'
    location: location
  }
}

module addUserScriptsFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'addUserScripts-fetch-image'
  params: {
    exists: addUserScriptsExists
    name: 'add-user-scripts'
  }
}

var addUserScriptsAppSettingsArray = filter(array(addUserScriptsDefinition.settings), i => i.name != '')
var addUserScriptsSecrets = map(filter(addUserScriptsAppSettingsArray, i => i.?secret != null), i => {
  name: i.name
  value: i.value
  secretRef: i.?secretRef ?? take(replace(replace(toLower(i.name), '_', '-'), '.', '-'), 32)
})
var addUserScriptsEnv = map(filter(addUserScriptsAppSettingsArray, i => i.?secret == null), i => {
  name: i.name
  value: i.value
})

module addUserScripts 'br/public:avm/res/app/container-app:0.8.0' = {
  name: 'addUserScripts'
  params: {
    name: 'add-user-scripts'
    ingressTargetPort: 80
    scaleMinReplicas: 1
    scaleMaxReplicas: 10
    secrets: {
      secureList:  union([
      ],
      map(addUserScriptsSecrets, secret => {
        name: secret.secretRef
        value: secret.value
      }))
    }
    containers: [
      {
        image: addUserScriptsFetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        name: 'main'
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: union([
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: monitoring.outputs.applicationInsightsConnectionString
          }
          {
            name: 'AZURE_CLIENT_ID'
            value: addUserScriptsIdentity.outputs.clientId
          }
          {
            name: 'PORT'
            value: '80'
          }
        ],
        addUserScriptsEnv,
        map(addUserScriptsSecrets, secret => {
            name: secret.name
            secretRef: secret.secretRef
        }))
      }
    ]
    managedIdentities:{
      systemAssigned: false
      userAssignedResourceIds: [addUserScriptsIdentity.outputs.resourceId]
    }
    registries:[
      {
        server: containerRegistry.outputs.loginServer
        identity: addUserScriptsIdentity.outputs.resourceId
      }
    ]
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    location: location
    tags: union(tags, { 'azd-service-name': 'add-user-scripts' })
  }
}

module fabricScriptsIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.2.1' = {
  name: 'fabricScriptsidentity'
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}fabricScripts-${resourceToken}'
    location: location
  }
}

module fabricScriptsFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'fabricScripts-fetch-image'
  params: {
    exists: fabricScriptsExists
    name: 'fabric-scripts'
  }
}

var fabricScriptsAppSettingsArray = filter(array(fabricScriptsDefinition.settings), i => i.name != '')
var fabricScriptsSecrets = map(filter(fabricScriptsAppSettingsArray, i => i.?secret != null), i => {
  name: i.name
  value: i.value
  secretRef: i.?secretRef ?? take(replace(replace(toLower(i.name), '_', '-'), '.', '-'), 32)
})
var fabricScriptsEnv = map(filter(fabricScriptsAppSettingsArray, i => i.?secret == null), i => {
  name: i.name
  value: i.value
})

module fabricScripts 'br/public:avm/res/app/container-app:0.8.0' = {
  name: 'fabricScripts'
  params: {
    name: 'fabric-scripts'
    ingressTargetPort: 80
    scaleMinReplicas: 1
    scaleMaxReplicas: 10
    secrets: {
      secureList:  union([
      ],
      map(fabricScriptsSecrets, secret => {
        name: secret.secretRef
        value: secret.value
      }))
    }
    containers: [
      {
        image: fabricScriptsFetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        name: 'main'
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: union([
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: monitoring.outputs.applicationInsightsConnectionString
          }
          {
            name: 'AZURE_CLIENT_ID'
            value: fabricScriptsIdentity.outputs.clientId
          }
          {
            name: 'PORT'
            value: '80'
          }
        ],
        fabricScriptsEnv,
        map(fabricScriptsSecrets, secret => {
            name: secret.name
            secretRef: secret.secretRef
        }))
      }
    ]
    managedIdentities:{
      systemAssigned: false
      userAssignedResourceIds: [fabricScriptsIdentity.outputs.resourceId]
    }
    registries:[
      {
        server: containerRegistry.outputs.loginServer
        identity: fabricScriptsIdentity.outputs.resourceId
      }
    ]
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    location: location
    tags: union(tags, { 'azd-service-name': 'fabric-scripts' })
  }
}

module indexScriptsIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.2.1' = {
  name: 'indexScriptsidentity'
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}indexScripts-${resourceToken}'
    location: location
  }
}

module indexScriptsFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'indexScripts-fetch-image'
  params: {
    exists: indexScriptsExists
    name: 'index-scripts'
  }
}

var indexScriptsAppSettingsArray = filter(array(indexScriptsDefinition.settings), i => i.name != '')
var indexScriptsSecrets = map(filter(indexScriptsAppSettingsArray, i => i.?secret != null), i => {
  name: i.name
  value: i.value
  secretRef: i.?secretRef ?? take(replace(replace(toLower(i.name), '_', '-'), '.', '-'), 32)
})
var indexScriptsEnv = map(filter(indexScriptsAppSettingsArray, i => i.?secret == null), i => {
  name: i.name
  value: i.value
})

module indexScripts 'br/public:avm/res/app/container-app:0.8.0' = {
  name: 'indexScripts'
  params: {
    name: 'index-scripts'
    ingressTargetPort: 80
    scaleMinReplicas: 1
    scaleMaxReplicas: 10
    secrets: {
      secureList:  union([
      ],
      map(indexScriptsSecrets, secret => {
        name: secret.secretRef
        value: secret.value
      }))
    }
    containers: [
      {
        image: indexScriptsFetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        name: 'main'
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: union([
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: monitoring.outputs.applicationInsightsConnectionString
          }
          {
            name: 'AZURE_CLIENT_ID'
            value: indexScriptsIdentity.outputs.clientId
          }
          {
            name: 'PORT'
            value: '80'
          }
        ],
        indexScriptsEnv,
        map(indexScriptsSecrets, secret => {
            name: secret.name
            secretRef: secret.secretRef
        }))
      }
    ]
    managedIdentities:{
      systemAssigned: false
      userAssignedResourceIds: [indexScriptsIdentity.outputs.resourceId]
    }
    registries:[
      {
        server: containerRegistry.outputs.loginServer
        identity: indexScriptsIdentity.outputs.resourceId
      }
    ]
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    location: location
    tags: union(tags, { 'azd-service-name': 'index-scripts' })
  }
}
// Create a keyvault to store secrets
module keyVault 'br/public:avm/res/key-vault/vault:0.6.1' = {
  name: 'keyvault'
  params: {
    name: '${abbrs.keyVaultVaults}${resourceToken}'
    location: location
    tags: tags
    enableRbacAuthorization: false
    accessPolicies: [
      {
        objectId: principalId
        permissions: {
          secrets: [ 'get', 'list' ]
        }
      }
      {
        objectId: appIdentity.outputs.principalId
        permissions: {
          secrets: [ 'get', 'list' ]
        }
      }
      {
        objectId: kmChartsFunctionIdentity.outputs.principalId
        permissions: {
          secrets: [ 'get', 'list' ]
        }
      }
      {
        objectId: kmRagFunctionIdentity.outputs.principalId
        permissions: {
          secrets: [ 'get', 'list' ]
        }
      }
      {
        objectId: addUserScriptsIdentity.outputs.principalId
        permissions: {
          secrets: [ 'get', 'list' ]
        }
      }
      {
        objectId: fabricScriptsIdentity.outputs.principalId
        permissions: {
          secrets: [ 'get', 'list' ]
        }
      }
      {
        objectId: indexScriptsIdentity.outputs.principalId
        permissions: {
          secrets: [ 'get', 'list' ]
        }
      }
    ]
    secrets: [
    ]
  }
}
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_KEY_VAULT_ENDPOINT string = keyVault.outputs.uri
output AZURE_KEY_VAULT_NAME string = keyVault.outputs.name
output AZURE_RESOURCE_APP_ID string = app.outputs.resourceId
output AZURE_RESOURCE_KM_CHARTS_FUNCTION_ID string = kmChartsFunction.outputs.resourceId
output AZURE_RESOURCE_KM_RAG_FUNCTION_ID string = kmRagFunction.outputs.resourceId
output AZURE_RESOURCE_ADD_USER_SCRIPTS_ID string = addUserScripts.outputs.resourceId
output AZURE_RESOURCE_FABRIC_SCRIPTS_ID string = fabricScripts.outputs.resourceId
output AZURE_RESOURCE_INDEX_SCRIPTS_ID string = indexScripts.outputs.resourceId
