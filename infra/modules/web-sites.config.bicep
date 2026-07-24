metadata name = 'Site App Settings'
metadata description = 'This module deploys a Site App Setting.'

@description('Conditional. The name of the parent site resource.')
param appName string

@description('Required. The name of the config.')
@allowed([
  'appsettings'
  'authsettings'
  'authsettingsV2'
  'azurestorageaccounts'
  'backup'
  'connectionstrings'
  'logs'
  'metadata'
  'pushsettings'
  'slotConfigNames'
  'web'
])
param name string

@description('Optional. The properties of the config.')
param properties object = {}

@description('Optional. Resource ID of the application insight to leverage for this resource.')
param applicationInsightResourceId string?

@description('Optional. The current app settings.')
param currentAppSettings {
  @description('Required. The key-values pairs of the current app settings.')
  *: string
} = {}

var appInsightsValues = !empty(applicationInsightResourceId)
  ? {
      APPLICATIONINSIGHTS_CONNECTION_STRING: applicationInsights!.properties.ConnectionString
    }
  : {}

var expandedProperties = union(currentAppSettings, properties, appInsightsValues)

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = if (!empty(applicationInsightResourceId)) {
  name: last(split(applicationInsightResourceId!, '/'))
  scope: resourceGroup(split(applicationInsightResourceId!, '/')[2], split(applicationInsightResourceId!, '/')[4])
}

resource app 'Microsoft.Web/sites@2023-12-01' existing = {
  name: appName
}

resource config 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: app
  #disable-next-line BCP225
  name: name
  properties: expandedProperties
}

@description('The name of the site config.')
output name string = config.name

@description('The resource ID of the site config.')
output resourceId string = config.id

@description('The resource group the site config was deployed into.')
output resourceGroupName string = resourceGroup().name
