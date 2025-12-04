param solutionLocation string
param keyVaultName string
param managedIdentityResourceId string
param managedIdentityClientId string
param storageAccount string
param enablePrivateNetworking bool = false
param subnetId string = ''

// var baseUrl = 'https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/'
var baseUrl = 'https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/helpdesk-dev/'

module uploadFiles 'br/public:avm/res/resources/deployment-script:0.5.1' = {
  name: take('avm.res.resources.deployment-script.uploadFiles', 64)
  params: {
    kind: 'AzureCLI'
    name: 'process_data_scripts'
    azCliVersion: '2.52.0'
    cleanupPreference: 'Always'
    location: solutionLocation
    managedIdentities: {
      userAssignedResourceIds: [
        managedIdentityResourceId
      ]
    }
    retentionInterval: 'P1D'
    runOnce: true
    primaryScriptUri: '${baseUrl}infra/scripts/process_data_scripts.sh'
    arguments: '${baseUrl} ${keyVaultName} ${managedIdentityClientId}'
    storageAccountResourceId: storageAccount
    subnetResourceIds: (enablePrivateNetworking && !empty(subnetId)) ? [
      subnetId
    ] : null
    timeout: 'PT1H'
  }
}
