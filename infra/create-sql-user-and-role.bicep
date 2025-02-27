targetScope = 'resourceGroup'

/*
** Create a User and Role on the SQL Database
** Copyright (C) 2023 Microsoft, Inc.
** All Rights Reserved
**
***************************************************************************
*/

// ========================================================================
// PARAMETERS
// ========================================================================

@description('The Azure region for the resource.')
param location string

@description('The tags to associate with this resource.')
param tags object = {}

@description('The database roles to assign to the user.')
param databaseRoles string[] = ['db_datareader']

@description('The ID of the managed identity to be used to run the script.')
param managedIdentityId string

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

// ========================================================================
// AZURE RESOURCES
// ========================================================================

resource createSqlUserAndRole 'Microsoft.Resources/deploymentScripts@2020-10-01' = [
  for databaseRole in databaseRoles: {
    name: 'sqlUserRole-${guid(principalId, databaseRole, sqlServerName, sqlDatabaseName)}'
    location: location
    tags: tags
    kind: 'AzurePowerShell'
    identity: {
      type: 'UserAssigned'
      userAssignedIdentities: {
        '${managedIdentityId}': {}
      }
    }
    properties: {
      forceUpdateTag: uniqueScriptId
      azPowerShellVersion: '7.4'
      retentionInterval: 'PT1H'
      cleanupPreference: 'OnSuccess' // No need to keep around any background resources if succeeded
      arguments: join(
        [
          '-SqlServerName \'${sqlServerName}\''
          '-SqlDatabaseName \'${sqlDatabaseName}\''
          '-ObjectId \'${principalId}\''
          '-DisplayName \'${principalName}\''
          '-DatabaseRole \'${databaseRole}\''
        ],
        ' '
      )
      scriptContent: loadTextContent('./scripts/add_user_scripts/create-sql-user-and-role.ps1')
    }
  }
]
