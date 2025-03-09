#Requires -Version 7.0

<#
.SYNOPSIS
    Creates a SQL user and assigns the user account to one or more roles.

.DESCRIPTION
    During an application deployment, the managed identity (and potentially the developer identity)
    must be added to the SQL database as a user and assigned to one or more roles. This script
    accomplishes this task using the owner-managed identity for authentication.

.PARAMETER SqlServerName
    The name of the Azure SQL Server resource.

.PARAMETER SqlDatabaseName
    The name of the Azure SQL Database where the user will be created.

.PARAMETER SqlUsers
    An array of objects containing:
      - principalId: The Client (Principal) ID (GUID) of the identity.
      - principalName: The display name of the identity.
      - databaseRoles: An array of roles to be assigned (e.g., ['db_datareader', 'db_datawriter']).

.PARAMETER ManagedIdentityClientId
    The Client ID of the managed identity that will authenticate to the SQL database.
#>

Param(
    [string] $SqlServerName,
    [string] $SqlDatabaseName,
    [array] $SqlUsers,
    [string] $ManagedIdentityClientId
)

function Resolve-Module($moduleName) {
    # If module is imported; say that and do nothing
    if (Get-Module | Where-Object { $_.Name -eq $moduleName }) {
        Write-Debug "Module $moduleName is already imported"
    } elseif (Get-Module -ListAvailable | Where-Object { $_.Name -eq $moduleName }) {
        Import-Module $moduleName
    } elseif (Find-Module -Name $moduleName | Where-Object { $_.Name -eq $moduleName }) {
        Install-Module $moduleName -Force -Scope CurrentUser
        Import-Module $moduleName
    } else {
        Write-Error "Module $moduleName not found"
        [Environment]::exit(1)
    }
}

###
### MAIN SCRIPT
###
Resolve-Module -moduleName Az.Resources
Resolve-Module -moduleName SqlServer

Connect-AzAccount -Identity -AccountId $ManagedIdentityClientId
$token = (Get-AzAccessToken -ResourceUrl https://database.windows.net/).Token
$SqlUsers1 = $SqlUsers | ConvertFrom-Json
$SqlUsers = $SqlUsers | ConvertFrom-Json
Write-Output "`nSQLUsers:`n$($SqlUsers)`n`n"
Write-Output "`nSQLUsers1:`n$($SqlUsers1)`n`n"

# Iterate through each user in the $SqlUsers array
foreach ($user in $SqlUsers) {
    $principalId = $user.principalId
    $principalName = $user.principalName
    $databaseRoles = $user.databaseRoles
    Write-Output "`nSQLUserprincipalId:`n$($principalId)`n`n"
    Write-Output "`nSQLUserprincipalName:`n$($principalName)`n`n"
    Write-Output "`nSQLUserdatabaseRoles:`n$($databaseRoles)`n`n"

    Write-Output "`nProcessing user: $principalName (Principal ID: $principalId) with roles: $($databaseRoles -join ', ')"

    # Construct SQL for user creation and role assignment
    $sql = @"
    DECLARE @username nvarchar(max) = N'$($principalName)';
    DECLARE @clientId uniqueidentifier = '$($principalId)';
    DECLARE @sid NVARCHAR(max) = CONVERT(VARCHAR(max), CONVERT(VARBINARY(16), @clientId), 1);
    DECLARE @cmd NVARCHAR(max) = N'CREATE USER [' + @username + '] WITH SID = ' + @sid + ', TYPE = E;';
    IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = @username)
    BEGIN
        EXEC(@cmd)
    END
"@

    Write-Output "`nSQL:`n$($sql)`n`n"

    Invoke-SqlCmd -ServerInstance $SqlServerName -Database $SqlDatabaseName -AccessToken $token -Query $sql -ErrorAction 'Stop'

    # Assign roles to the user
    foreach ($role in $databaseRoles) {
        $roleSql = "EXEC sp_addrolemember '$role', [$principalName];"
        Write-Output "`nAssigning role $role to user $principalName"
        Invoke-SqlCmd -ServerInstance $SqlServerName -Database $SqlDatabaseName -AccessToken $token -Query $roleSql -ErrorAction 'Stop'
    }

    Write-Output "`nUser $principalName setup completed successfully."
}

Write-Output "`nAll users processed successfully."