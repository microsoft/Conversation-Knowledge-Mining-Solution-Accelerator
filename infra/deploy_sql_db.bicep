@description('Required. Specifies the location for resources.')
param solutionLocation string

@description('Required. Contains KeyVault Name.')
param keyVaultName string

@description('Required. Contains Managed Identity Name.')
param managedIdentityName string

@description('Required. Contains Server Name.')
param serverName string

@description('Required. Contains SQL DB Name.')
param sqlDBName string

@description('Required. List of SQL Users.')
param sqlUsers array = []

@description('Optional. Tags to be applied to the resources.')
param tags object = {}

var location = solutionLocation

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: managedIdentityName
}

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: serverName
  location: location
  kind: 'v12.0'
  properties: {
    publicNetworkAccess: 'Enabled'
    version: '12.0'
    restrictOutboundNetworkAccess: 'Disabled'
    minimalTlsVersion: '1.2'
    administrators: {
      login: managedIdentityName
      sid: managedIdentity.properties.principalId
      tenantId: subscription().tenantId
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: true
    }
  }
  tags : tags
}

resource firewallRule 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  name: 'AllowSpecificRange'
  parent: sqlServer
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '255.255.255.255'
  }
}

resource AllowAllWindowsAzureIps 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  name: 'AllowAllWindowsAzureIps'
  parent: sqlServer
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource sqlDB 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: sqlDBName
  location: location
  sku: {
    name: 'GP_S_Gen5'
    tier: 'GeneralPurpose'
    family: 'Gen5'
    capacity: 2
  }
  kind: 'v12.0,user,vcore,serverless'
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    autoPauseDelay: 60
    minCapacity: 1
    readScale: 'Disabled'
    zoneRedundant: false
  }
  tags : tags
}

module sqluser 'create-sql-user-and-role.bicep' = [
  for user in sqlUsers: {
    name: 'sqluser-${guid(solutionLocation, user.principalId, user.principalName, sqlDB.name, sqlServer.name)}'
    params: {
      managedIdentityName: managedIdentityName
      location: solutionLocation
      sqlDatabaseName: sqlDB.name
      sqlServerName: sqlServer.name
      principalId: user.principalId
      principalName: user.principalName
      databaseRoles: user.databaseRoles
    }
  }
]

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: keyVaultName
}

resource sqldbServerEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'SQLDB-SERVER'
  properties: {
    value: '${serverName}${environment().suffixes.sqlServerHostname}'
  }
  tags : tags
}

resource sqldbDatabaseEntry 'Microsoft.KeyVault/vaults/secrets@2021-11-01-preview' = {
  parent: keyVault
  name: 'SQLDB-DATABASE'
  properties: {
    value: sqlDBName
  }
  tags : tags
}

@description('Contains SQL Server Name.')
output sqlServerName string = '${serverName}.database.windows.net'

@description('Contains SQL DB Name.')
output sqlDbName string = sqlDBName
