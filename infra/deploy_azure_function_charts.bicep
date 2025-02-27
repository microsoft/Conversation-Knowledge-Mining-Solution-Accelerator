@description('Specifies the location for resources.')
param solutionName string 
param solutionLocation string
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
var functionAppName = '${solutionName}-charts-fn'
var dockerImage = 'DOCKER|kmcontainerreg.azurecr.io/km-charts-function:${imageTag}'
var environmentName = '${solutionName}-charts-fn-env'

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


