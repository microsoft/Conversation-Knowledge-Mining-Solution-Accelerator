targetScope = 'resourceGroup'

@description('The Azure region for the resource.')
param location string

@description('The tags to associate with this resource.')
param tags object = {}

@description('The database roles to assign to the user.')
param databaseRoles string[] = ['db_datareader']

@description('The name of the User Assigned Managed Identity to be used.')
param managedIdentityName string

@description('The principal (or object) ID of the user to create.')
param principalId string

@description('The name of the user to create.')
param principalName string

@description('The name of the SQL Database resource.')
param sqlDatabaseName string

@description('The name of the SQL Server resource.')
param sqlServerName string

@description('Do not set - unique script ID to force the script to run.')
param uniqueScriptId string = newGuid()

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: managedIdentityName
}

resource createSqlUserAndRole 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'sqlUserRole-${guid(principalId, sqlServerName, sqlDatabaseName)}'
  location: location
  tags: tags
  kind: 'AzurePowerShell'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    forceUpdateTag: uniqueScriptId
    azPowerShellVersion: '7.2'
    retentionInterval: 'PT1H'
    cleanupPreference: 'OnSuccess'
    arguments: join(
      [
        '-SqlServerName \'${sqlServerName}\''
        '-SqlDatabaseName \'${sqlDatabaseName}\''
        '-ClientId \'${principalId}\''
        '-DisplayName \'${principalName}\''
        '-DatabaseRoles \'${join(databaseRoles, ',')}\''
      ],
      ' '
    )
    scriptContent: loadTextContent('./scripts/add_user_scripts/create-sql-user-and-role.ps1')
  }
}
