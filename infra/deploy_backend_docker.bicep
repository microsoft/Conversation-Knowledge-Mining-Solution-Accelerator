param imageTag string
param applicationInsightsId string

@description('Solution Location')
param solutionLocation string

@secure()
param appSettings object = {}
param appServicePlanId string
param userassignedIdentityId string
param aiProjectName string
param keyVaultName string
param aiServicesName string

var imageName = 'DOCKER|kmcontainerreg.azurecr.io/km-api:${imageTag}'
//var name = '${solutionName}-api'
param name string 
var reactAppLayoutConfig ='''{
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

module appService 'deploy_app_service.bicep' = {
  name: '${name}-app-module'
  params: {
    solutionName: name
    solutionLocation:solutionLocation
    appServicePlanId: appServicePlanId
    appImageName: imageName
    userassignedIdentityId:userassignedIdentityId
    appSettings: union(
      appSettings,
      {
        APPINSIGHTS_INSTRUMENTATIONKEY: reference(applicationInsightsId, '2015-05-01').InstrumentationKey
        REACT_APP_LAYOUT_CONFIG: reactAppLayoutConfig
      }
    )
  }
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2022-08-15' existing = {
  name: appSettings.AZURE_COSMOSDB_ACCOUNT
}

resource contributorRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-05-15' existing = {
  parent: cosmos
  name: '00000000-0000-0000-0000-000000000002'
}

resource role 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2022-05-15' = {
  parent: cosmos
  name: guid(contributorRoleDefinition.id, cosmos.id)
  properties: {
    principalId: appService.outputs.identityPrincipalId
    roleDefinitionId: contributorRoleDefinition.id
    scope: cosmos.id
  }
}

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiServicesName
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  parent: aiServices
  name: aiProjectName
}

resource aiDeveloper 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '64702f94-c441-49e6-a78b-ef80e0188fee'
}

resource aiDeveloperAccessProj 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appService.name, aiProject.id, aiDeveloper.id)
  scope: aiProject
  properties: {
    roleDefinitionId: aiDeveloper.id
    principalId: appService.outputs.identityPrincipalId
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: keyVaultName
}

resource keyVaultSecretsUser 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '4633458b-17de-408a-b874-0445c86b69e6'
}

resource keyVaultSecretsUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appService.name, keyVault.name, keyVaultSecretsUser.id)
  scope: keyVault
  properties: {
    roleDefinitionId: keyVaultSecretsUser.id
    principalId: appService.outputs.identityPrincipalId
  }
}

resource aiUser 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
}

resource aiUserAccessProj 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appService.name, aiProject.id, aiUser.id)
  scope: aiProject
  properties: {
    roleDefinitionId: aiUser.id
    principalId: appService.outputs.identityPrincipalId
  }
}

resource aiUserAccessFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appService.name, aiServices.id, aiUser.id)
  scope: aiServices
  properties: {
    roleDefinitionId: aiUser.id
    principalId: appService.outputs.identityPrincipalId
  }
}

output appUrl string = appService.outputs.appUrl
output reactAppLayoutConfig string = reactAppLayoutConfig
output appInsightInstrumentationKey string = reference(applicationInsightsId, '2015-05-01').InstrumentationKey
