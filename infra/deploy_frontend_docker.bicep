param imageTag string
param acrName string
param applicationInsightsId string

@description('Solution Location')
param solutionLocation string

@secure()
param appSettings object = {}
param appServicePlanId string

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
    appSettings: union(
      appSettings,
      {
        APPINSIGHTS_INSTRUMENTATIONKEY: reference(applicationInsightsId, '2015-05-01').InstrumentationKey
      }
    )
  }
}

output appUrl string = appService.outputs.appUrl
