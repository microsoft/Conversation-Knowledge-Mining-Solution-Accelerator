param imageTag string
param acrName string
param applicationInsightsId string

@description('Solution Location')
param solutionLocation string

@secure()
param appSettings object = {}
param appServicePlanId string
param useLocalBuild string

var imageName = 'DOCKER|${acrName}.azurecr.io/km-app:${imageTag}'
//var name = '${solutionName}-app'
param name string
module appService 'deploy_app_service.bicep' = {
  name: '${name}-app-module'
  params: {
    solutionLocation:solutionLocation
    solutionName: name
    appServicePlanId: appServicePlanId
    appImageName: imageName
    useLocalBuild: useLocalBuild
    appSettings: union(
      appSettings,
      {
        APPINSIGHTS_INSTRUMENTATIONKEY: reference(applicationInsightsId, '2015-05-01').InstrumentationKey
      }
    )
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2021-09-01' existing = if (useLocalBuild == 'true') {
  name: acrName
}

resource AcrPull 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = if (useLocalBuild == 'true') {
  name: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
}

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useLocalBuild == 'true') {
  name: guid(appService.name, AcrPull.id)
  scope: containerRegistry
  properties: {
    roleDefinitionId: AcrPull.id
    principalId: appService.outputs.identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output appUrl string = appService.outputs.appUrl
