param imageTag string
param applicationInsightsId string
param solutionName string
@secure()
param appSettings object = {}
param appServicePlanId string
@secure()
 param azureOpenAIKey string
 @secure()
 param azureAiProjectConnString string
 @secure()
 param azureSearchAdminKey string
param userassignedIdentityId string
param aiProjectName string

var imageName = 'DOCKER|kmcontainerreg.azurecr.io/km-api:${imageTag}'
var name = '${solutionName}-api'

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
    appServicePlanId: appServicePlanId
    appImageName: imageName
    userassignedIdentityId:userassignedIdentityId
    appSettings: union(
      appSettings,
      {
        AZURE_OPENAI_API_KEY: azureOpenAIKey
        AZURE_AI_SEARCH_API_KEY: azureSearchAdminKey
        AZURE_AI_PROJECT_CONN_STRING:azureAiProjectConnString
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

resource aiHubProject 'Microsoft.MachineLearningServices/workspaces@2024-01-01-preview' existing = {
  name: aiProjectName
}

resource aiDeveloper 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '64702f94-c441-49e6-a78b-ef80e0188fee'
}

resource aiDeveloperAccessProj 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appService.name, aiHubProject.id, aiDeveloper.id)
  scope: aiHubProject
  properties: {
    roleDefinitionId: aiDeveloper.id
    principalId: appService.outputs.identityPrincipalId
  }
}

output appUrl string = appService.outputs.appUrl
