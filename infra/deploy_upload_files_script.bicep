@description('Specifies the location for resources.')
param solutionLocation string
param baseUrl string
param managedIdentityResourceId string
param managedIdentityClientId string
param storageAccountName string
param containerName string

resource copy_demo_Data 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  kind:'AzureCLI'
  name: 'copy_demo_Data'
  location: solutionLocation
  identity:{
    type:'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityResourceId}' : {}
    }
  }
  properties: {
    azCliVersion: '2.52.0'
    primaryScriptUri: '${baseUrl}infra/scripts/copy_kb_files.sh'
    arguments: '${storageAccountName} ${containerName} ${baseUrl} ${managedIdentityClientId}'
    timeout: 'PT1H'
    retentionInterval: 'PT1H'
    cleanupPreference:'OnSuccess'
  }
}
