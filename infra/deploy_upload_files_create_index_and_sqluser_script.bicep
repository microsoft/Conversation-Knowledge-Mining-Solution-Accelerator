@description('Solution Name')
param solutionName string
@description('Specifies the location for resources.')
param solutionLocation string
param baseUrl string
param managedIdentityObjectId string
param managedIdentityClientId string
param storageAccountName string
param containerName string
param containerAppName string = '${ solutionName }containerapp'
param environmentName string = '${ solutionName }containerappenv'
param imageName string = 'python:3.11-alpine'
param run_all_scripts string = '${baseUrl}infra/scripts/run_all_scripts.sh'
param setupCopyKbFiles string = '${baseUrl}infra/scripts/copy_kb_files.sh'
param setupCreateIndexScriptsUrl string = '${baseUrl}infra/scripts/run_create_index_scripts.sh'
param createSqlUserAndRoleScriptsUrl string = '${baseUrl}infra/scripts/add_user_scripts/create-sql-user-and-role.ps1'
param keyVaultName string
param sqlServerName string
param sqlDbName string
param sqlUsers array = [
]

resource containerAppEnv 'Microsoft.App/managedEnvironments@2022-03-01' = {
  name: environmentName
  location: solutionLocation
  properties: {
    zoneRedundant: false
  }
}

resource containerApp 'Microsoft.App/containerApps@2022-03-01' = {
  name: containerAppName
  location: solutionLocation
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityObjectId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 80
      }
 
    }
    template: {
      containers: [
        {
          name: containerAppName
          image: imageName
          resources: {
            cpu: 1
            memory: '2.0Gi'
          }
          command: [
            '/bin/sh', '-c', 'mkdir -p /scripts && apk add --no-cache curl && curl -s -o /scripts/run_all_scripts.sh ${run_all_scripts} && chmod +x /scripts/run_all_scripts.sh && sh -x /scripts/run_all_scripts.sh ${storageAccountName} ${containerName} ${baseUrl} ${managedIdentityClientId} ${setupCopyKbFiles} ${setupCreateIndexScriptsUrl} ${createSqlUserAndRoleScriptsUrl} ${keyVaultName} ${sqlServerName} ${sqlDbName} ${sqlUsers}'
          ]
          env: [
            {
              name: 'STORAGE_ACCOUNT_NAME'
              value: storageAccountName
            }
            {
              name: 'CONTAINER_NAME'
              value: containerName
            }
            {
              name:'APPSETTING_WEBSITE_SITE_NAME'
              value:'DUMMY'
            }
          ]
        }
      ]
    }
  }
}
