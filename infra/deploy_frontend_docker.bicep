@description('Required. Contains the Image Tag.')
param imageTag string

@description('Required. Contains ACR Name.')
param acrName string

@description('Required. Contains Application Insights ID.')
param applicationInsightsId string

@description('Required. Specifies the location for resources.')
param solutionLocation string

@secure()
@description('Required. Contains App Settings.')
param appSettings object = {}

@description('Required. Contains App Service Plan ID.')
param appServicePlanId string

var imageName = 'DOCKER|${acrName}.azurecr.io/km-app:${imageTag}'
//var name = '${solutionName}-app'
@description('Required. The name of the app service resource within the current resource group scope.')
param name string

module appService 'deploy_app_service.bicep' = {
  name: '${name}-app-module'
  params: {
    solutionLocation:solutionLocation
    solutionName: name
    appServicePlanId: appServicePlanId
    appImageName: imageName
    appSettings: union(
      appSettings,
      {
        APPINSIGHTS_INSTRUMENTATIONKEY: reference(applicationInsightsId, '2015-05-01').InstrumentationKey
      }
    )
  }
}

@description('Contains App URL.')
output appUrl string = appService.outputs.appUrl
