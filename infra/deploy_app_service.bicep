// ========== Key Vault ========== //
targetScope = 'resourceGroup'

@minLength(3)
@maxLength(16)
@description('Required. Contains Solution Name.')
param solutionName string

@description('Required. Specifies the location for resources.')
param solutionLocation string

@secure()
@description('Required. Contains App Settings.')
param appSettings object = {}

@description('Required. Contains App Service Plan ID.')
param appServicePlanId string

@description('Required. Contains App Image Name.')
param appImageName string

@description('Optional. Contains User Assigned Identity ID.')
param userassignedIdentityId string = ''

@description('Optional. Tags to be applied to the resources.')
param tags object = {}

resource appService 'Microsoft.Web/sites@2020-06-01' = {
  name: solutionName
  location: solutionLocation
  tags : tags
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


@description('Contains Identity Principle ID.')
output identityPrincipalId string = appService.identity.principalId

@description('Contains App URL.')
output appUrl string = 'https://${solutionName}.azurewebsites.net'

