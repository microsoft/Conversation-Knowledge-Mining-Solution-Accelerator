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
param setupCopyKbFiles string = '${baseUrl}infra/scripts/copy_kb_files.sh'
param setupCreateIndexScriptsUrl string = '${baseUrl}infra/scripts/run_create_index_scripts.sh'
param keyVaultName string

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
            '/bin/sh', '-c', 'mkdir -p /scripts && apk add --no-cache curl bash jq py3-pip gcc musl-dev libffi-dev openssl-dev python3-dev && pip install --upgrade azure-cli && curl -s -o /scripts/copy_kb_files.sh ${setupCopyKbFiles} && chmod +x /scripts/copy_kb_files.sh && sh -x /scripts/copy_kb_files.sh ${storageAccountName} ${containerName} ${baseUrl} ${managedIdentityClientId} && curl -s -o /scripts/run_create_index_scripts.sh ${setupCreateIndexScriptsUrl} && chmod +x /scripts/run_create_index_scripts.sh && sh -x /scripts/run_create_index_scripts.sh ${baseUrl} ${keyVaultName} ${managedIdentityClientId}'
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
