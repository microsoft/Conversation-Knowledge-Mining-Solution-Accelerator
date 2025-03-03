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

.PARAMETER ClientId
    The Client (Principal) ID (GUID) of the identity to be added.

.PARAMETER DisplayName
    The Object (Principal) display name of the identity to be added.

.PARAMETER ManagedIdentityClientId
    The Client ID of the managed identity that will authenticate to the SQL database.

.PARAMETER DatabaseRole
    The database role that should be assigned to the user (e.g., db_datareader, db_datawriter, db_owner).
#>

Param(
    [string] $SqlServerName,
    [string] $SqlDatabaseName,
    [string] $ClientId,
    [string] $DisplayName,
    [string] $ManagedIdentityClientId,
    [string] $DatabaseRole
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

$sql = @"
DECLARE @username nvarchar(max) = N'$($DisplayName)';
DECLARE @clientId uniqueidentifier = '$($ClientId)';
DECLARE @sid NVARCHAR(max) = CONVERT(VARCHAR(max), CONVERT(VARBINARY(16), @clientId), 1);
DECLARE @cmd NVARCHAR(max) = N'CREATE USER [' + @username + '] WITH SID = ' + @sid + ', TYPE = E;';
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = @username)
BEGIN
    EXEC(@cmd)
END
EXEC sp_addrolemember '$($DatabaseRole)', @username;
"@

Write-Output "`nSQL:`n$($sql)`n`n"

Connect-AzAccount -Identity -AccountId $ManagedIdentityClientId
$token = (Get-AzAccessToken -ResourceUrl https://database.windows.net/).Token
Invoke-SqlCmd -ServerInstance "$SqlServerName" -Database $SqlDatabaseName -AccessToken $token -Query $sql -ErrorAction 'Stop'