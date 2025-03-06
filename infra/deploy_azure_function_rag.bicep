@description('Specifies the location for resources.')
param solutionName string 
param solutionLocation string
@secure()
param azureOpenAIApiKey string
param azureOpenAIApiVersion string
param azureOpenAIEndpoint string
param azureOpenAIDeploymentModel string
@secure()
param azureAiProjectConnString string
param aiProjectName string
@secure()
param azureSearchAdminKey string
param azureSearchServiceEndpoint string
param azureSearchIndex string
param sqlServerName string
param sqlDbName string
param sqlDbUser string
@secure()
param sqlDbPwd string
// param managedIdentityObjectId string
param imageTag string
param storageAccountName string
param userassignedIdentityId string
param userassignedIdentityClientId string

var functionAppName = '${solutionName}-rag-fn'
var dockerImage = 'DOCKER|kmcontainerreg.azurecr.io/km-rag-function:${imageTag}'
var environmentName = '${solutionName}-rag-fn-env'

// var sqlServerName = 'nc2202-sql-server.database.windows.net'
// var sqlDbName = 'nc2202-sql-db'
// var sqlDbUser = 'sqladmin'
// var sqlDbPwd = 'TestPassword_1234'

resource managedenv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: solutionLocation
  properties: {
    zoneRedundant: false
    kedaConfiguration: {}
    daprConfiguration: {}
    customDomainConfiguration: {}
    workloadProfiles: [
      {
        workloadProfileType: 'Consumption'
        name: 'Consumption'
      }
    ]
    peerAuthentication: {
      mtls: {
        enabled: false
      }
    }
    peerTrafficConfiguration: {
      encryption: {
        enabled: false
      }
    }
  }
}

resource azurefn 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: solutionLocation
  kind: 'functionapp,linux,container,azurecontainerapps'
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${userassignedIdentityId}': {}
    }
  }
  properties: {
    siteConfig: {
      appSettings: [
        {
          name: 'AzureWebJobsStorage__accountname'
          value: storageAccountName
        }
        {
          name: 'PYTHON_ENABLE_INIT_INDEXING'
          value: '1'
        }
        {
          name: 'PYTHON_ISOLATE_WORKER_DEPENDENCIES'
          value: '1'
        }
        {
          name: 'SQLDB_DATABASE'
          value: sqlDbName
        }
        {
          name: 'SQLDB_PASSWORD'
          value: sqlDbPwd
        }
        {
          name: 'SQLDB_SERVER'
          value: sqlServerName
        }
        {
          name: 'SQLDB_USERNAME'
          value: sqlDbUser
        }
        {
          name: 'AZURE_OPEN_AI_ENDPOINT'
          value: azureOpenAIEndpoint
        }
        {
          name: 'AZURE_OPEN_AI_API_KEY'
          value: azureOpenAIApiKey
        }
        {
          name: 'AZURE_AI_PROJECT_CONN_STRING'
          value: azureAiProjectConnString
        }
        {
          name: 'OPENAI_API_VERSION'
          value: azureOpenAIApiVersion
        }
        {
          name: 'AZURE_OPEN_AI_DEPLOYMENT_MODEL'
          value: azureOpenAIDeploymentModel
        }
        {
          name: 'AZURE_AI_SEARCH_ENDPOINT'
          value: azureSearchServiceEndpoint
        }
        {
          name: 'AZURE_AI_SEARCH_API_KEY'
          value: azureSearchAdminKey
        }
        {
          name: 'AZURE_AI_SEARCH_INDEX'
          value: azureSearchIndex
        }
        {
          name: 'SQLDB_USER_MID'
          value: userassignedIdentityClientId
        }
      ]
      linuxFxVersion: dockerImage
      functionAppScaleLimit: 10
      minimumElasticInstanceCount: 0
    }
    managedEnvironmentId: managedenv.id
    workloadProfileName: 'Consumption'
    resourceConfig: {
      cpu: 1
      memory: '2Gi'
    }
    storageAccountRequired: false
  }
}

resource aiHubProject 'Microsoft.MachineLearningServices/workspaces@2024-01-01-preview' existing = {
  name: aiProjectName
}

resource aiDeveloper 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '64702f94-c441-49e6-a78b-ef80e0188fee'
}

resource aiDeveloperAccessProj 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(azurefn.id, aiHubProject.id, aiDeveloper.id)
  scope: aiHubProject
  properties: {
    roleDefinitionId: aiDeveloper.id
    principalId: azurefn.identity.principalId
  }
}


