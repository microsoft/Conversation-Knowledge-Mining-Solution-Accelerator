// ========== Key Vault ========== //
targetScope = 'resourceGroup'

@description('Solution Name')
param solutionName string

@description('Solution Location')
param solutionLocation string

@secure()
param appSettings object = {}
param appServicePlanId string
param appImageName string
param userassignedIdentityId string = ''

resource appService 'Microsoft.Web/sites@2020-06-01' = {
  name: solutionName
  location: solutionLocation
  identity: userassignedIdentityId == '' ? {
    type: 'SystemAssigned'
  } : {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${userassignedIdentityId}': {}
    }
  }  
  properties: {
    serverFarmId: appServicePlanId
    siteConfig: {
      alwaysOn: true
      ftpsState: 'Disabled'
      linuxFxVersion: appImageName
    }
  }
  resource basicPublishingCredentialsPoliciesFtp 'basicPublishingCredentialsPolicies' = {
    name: 'ftp'
    properties: {
      allow: false
    }
  }
  resource basicPublishingCredentialsPoliciesScm 'basicPublishingCredentialsPolicies' = {
    name: 'scm'
    properties: {
      allow: false
    }
  }
}

module configAppSettings 'deploy_appservice-appsettings.bicep' = {
  name: '${appService.name}-appSettings'
  params: {
    name: appService.name
    appSettings: appSettings
  }
}

resource configLogs 'Microsoft.Web/sites/config@2022-03-01' = {
  name: 'logs'
  parent: appService
  properties: {
    applicationLogs: { fileSystem: { level: 'Verbose' } }
    detailedErrorMessages: { enabled: true }
    failedRequestsTracing: { enabled: true }
    httpLogs: { fileSystem: { enabled: true, retentionInDays: 1, retentionInMb: 35 } }
  }
  dependsOn: [configAppSettings]
}

output identityPrincipalId string = appService.identity.principalId
output appUrl string = 'https://${solutionName}.azurewebsites.net'

