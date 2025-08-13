@description('Required. Specifies the location for resources.')
param solutionLocation string

@description('Required. Contains Base URL.')
param baseUrl string

@description('Required. Contains Managed Identity Resource ID.')
param managedIdentityResourceId string

@description('Required. Contains Managed Identity Client ID.')
param managedIdentityClientId string

@description('Required. Contains Storage Account Name.')
param storageAccountName string

@description('Required. Contains COntainer Name.')
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
