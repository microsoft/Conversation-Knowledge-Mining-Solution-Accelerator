// ========== Key Vault ========== //
targetScope = 'resourceGroup'

@minLength(3)
@maxLength(15)
@description('Solution Name')
param solutionName string

@description('Solution Location')
param solutionLocation string

param identity string

@description('Name of App Service plan')
param HostingPlanName string = '${ solutionName }-app-service-plan'

@description('The pricing tier for the App Service plan')
@allowed(
  ['F1', 'D1', 'B1', 'B2', 'B3', 'S1', 'S2', 'S3', 'P1', 'P2', 'P3', 'P4','P0v3']
)
// param HostingPlanSku string = 'B1'

param HostingPlanSku string = 'P0v3'

@description('Name of Web App')
param WebsiteName string = '${ solutionName }-app-service'

@description('Name of Application Insights')
param ApplicationInsightsName string = '${ solutionName }-app-insights'

@description('Azure OpenAI Model Deployment Name')
param AzureOpenAIModel string

@description('Azure Open AI Endpoint')
param AzureOpenAIEndpoint string = ''

@description('Azure OpenAI Key')
@secure()
param AzureOpenAIKey string

param azureOpenAIApiVersion string
param AZURE_OPENAI_RESOURCE string = ''
param CHARTS_URL string = ''
param FILTERS_URL string = ''
param USE_GRAPHRAG string = ''
param GRAPHRAG_URL string = ''
param RAG_URL string = ''
param USE_CHAT_HISTORY_ENABLED string = ''

@description('Azure Cosmos DB Account')
param AZURE_COSMOSDB_ACCOUNT string = ''

@description('Azure Cosmos DB Account Key')
@secure()
param AZURE_COSMOSDB_ACCOUNT_KEY string = ''

@description('Azure Cosmos DB Conversations Container')
param AZURE_COSMOSDB_CONVERSATIONS_CONTAINER string = ''

@description('Azure Cosmos DB Database')
param AZURE_COSMOSDB_DATABASE string = ''

@description('Enable feedback in Cosmos DB')
param AZURE_COSMOSDB_ENABLE_FEEDBACK string = 'True'

param imageTag string
// var WebAppImageName = 'DOCKER|byoaiacontainer.azurecr.io/byoaia-app:latest'

// var WebAppImageName = 'DOCKER|ncwaappcontainerreg1.azurecr.io/ncqaappimage:v1.0.0'

var WebAppImageName = 'DOCKER|kmcontainerreg.azurecr.io/km-app:${imageTag}'

resource HostingPlan 'Microsoft.Web/serverfarms@2020-06-01' = {
  name: HostingPlanName
  location: resourceGroup().location
  sku: {
    name: HostingPlanSku
  }
  properties: {
    name: HostingPlanName
    reserved: true
  }
  kind: 'linux'
}
var REACT_APP_LAYOUT_CONFIG ='''{
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

resource Website 'Microsoft.Web/sites@2020-06-01' = {
  name: WebsiteName
  location: resourceGroup().location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: HostingPlanName
    siteConfig: {
      appSettings: [
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: reference(ApplicationInsights.id, '2015-05-01').InstrumentationKey
        }
        {
          name: 'AZURE_OPENAI_API_VERSION'
          value: azureOpenAIApiVersion
        }
        {
          name: 'AZURE_OPENAI_DEPLOYMENT_NAME'
          value: AzureOpenAIModel
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: AzureOpenAIEndpoint
        }
        {
          name: 'AZURE_OPENAI_API_KEY'
          value: AzureOpenAIKey
        }
        {
          name: 'AZURE_OPENAI_RESOURCE'
          value: AZURE_OPENAI_RESOURCE
        }
        {
          name: 'AZURE_OPENAI_PREVIEW_API_VERSION'
          value: azureOpenAIApiVersion
        }
        {
          name: 'USE_CHAT_HISTORY_ENABLED'
          value: USE_CHAT_HISTORY_ENABLED
        }
        {name: 'USE_GRAPHRAG', value: USE_GRAPHRAG}
        {name: 'CHART_DASHBOARD_URL', value: CHARTS_URL}
        {name: 'CHART_DASHBOARD_FILTERS_URL', value: FILTERS_URL}
        {name: 'GRAPHRAG_URL', value: GRAPHRAG_URL}
        {name: 'RAG_URL', value: RAG_URL}
        {name: 'REACT_APP_LAYOUT_CONFIG', value: REACT_APP_LAYOUT_CONFIG}
        {name: 'AZURE_COSMOSDB_ACCOUNT'
          value: AZURE_COSMOSDB_ACCOUNT
        }
        {name: 'AZURE_COSMOSDB_ACCOUNT_KEY'
          value: '' //AZURE_COSMOSDB_ACCOUNT_KEY
        }
        {name: 'AZURE_COSMOSDB_CONVERSATIONS_CONTAINER'
          value: AZURE_COSMOSDB_CONVERSATIONS_CONTAINER
        }
        {name: 'AZURE_COSMOSDB_DATABASE'
          value: AZURE_COSMOSDB_DATABASE
        }
        {name: 'AZURE_COSMOSDB_ENABLE_FEEDBACK'
          value: AZURE_COSMOSDB_ENABLE_FEEDBACK
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'UWSGI_PROCESSES'
          value: '2'
        }
        {
          name: 'UWSGI_THREADS'
          value: '2'
        }
      ]
      linuxFxVersion: WebAppImageName
    }
  }
  dependsOn: [HostingPlan]
}

resource ApplicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: ApplicationInsightsName
  location: resourceGroup().location
  tags: {
    'hidden-link:${resourceId('Microsoft.Web/sites',ApplicationInsightsName)}': 'Resource'
  }
  properties: {
    Application_Type: 'web'
  }
  kind: 'web'
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2022-08-15' existing = {
  name: AZURE_COSMOSDB_ACCOUNT
}

resource contributorRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-05-15' existing = {
  name: '${AZURE_COSMOSDB_ACCOUNT}/00000000-0000-0000-0000-000000000002'
}

resource role 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2022-05-15' = {
  parent: cosmos
  name: guid(contributorRoleDefinition.id, cosmos.id)
  properties: {
    principalId: Website.identity.principalId
    roleDefinitionId: contributorRoleDefinition.id
    scope: cosmos.id
  }
  dependsOn: [Website]
}


