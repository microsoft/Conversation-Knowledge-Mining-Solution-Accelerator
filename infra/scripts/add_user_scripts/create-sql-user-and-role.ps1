#Requires -Version 7.0

<#
.SYNOPSIS
    Creates a SQL user and assigns the user account to one or more roles.

.DESCRIPTION
    During an application deployment, the managed identity (and potentially the developer identity)
    must be added to the SQL database as a user and assigned to one or more roles.  This script
    does exactly that using the owner managed identity.

.PARAMETER SqlServerName
    The name of the SQL Server resource
.PARAMETER SqlDatabaseName
    The name of the SQL Database resource
.PARAMETER ObjectId
    The Object (Principal) ID of the user to be added.
.PARAMETER DisplayName
    The Object (Principal) display name of the user to be added.
.PARAMETER DatabaseRole
    The database role that needs to be assigned to the user.
#>

Param(
    [string] $SqlServerName,
    [string] $SqlDatabaseName,
    [string] $ObjectId,
    [string] $DisplayName,
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
DECLARE @clientId uniqueidentifier = '$($ObjectId)';
DECLARE @sid NVARCHAR(max) = CONVERT(VARCHAR(max), CONVERT(VARBINARY(16), @clientId), 1);
DECLARE @cmd NVARCHAR(max) = N'CREATE USER [' + @username + '] WITH SID = ' + @sid + ', TYPE = E;';
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = @username)
BEGIN
    EXEC(@cmd)
END
EXEC sp_addrolemember '$($DatabaseRole)', @username;
"@

Write-Output "`nSQL:`n$($sql)`n`n"

$token = (Get-AzAccessToken -ResourceUrl https://database.windows.net/).Token
Invoke-SqlCmd -ServerInstance "$SqlServerName.database.windows.net" -Database $SqlDatabaseName -AccessToken $token -Query $sql -ErrorAction 'Stop'