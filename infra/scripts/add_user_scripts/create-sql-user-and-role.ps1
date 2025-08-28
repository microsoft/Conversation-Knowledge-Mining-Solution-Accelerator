#Requires -Version 7.2

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

.PARAMETER DatabaseRoles
    A comma-separated string of database roles to assign (e.g., 'db_datareader,db_datawriter')
#>

Param(
    [string] $SqlServerName,
    [string] $SqlDatabaseName,
    [string] $ClientId,
    [string] $DisplayName,
    [string] $DatabaseRoles
)

# Using specific version of SqlServer module to avoid issues with newer versions
$SqlServerModuleVersion = "22.3.0"

function Resolve-Module($moduleName) {
    # If module is imported; say that and do nothing
    if (Get-Module | Where-Object { $_.Name -eq $moduleName }) {
        Write-Debug "Module $moduleName is already imported"
    } elseif (Get-Module -ListAvailable | Where-Object { $_.Name -eq $moduleName }) {
        Import-Module $moduleName
    } elseif (Find-Module -Name $moduleName | Where-Object { $_.Name -eq $moduleName }) {
        # Use specific version for SqlServer
        if ($moduleName -eq "SqlServer") {
            Install-Module -Name $moduleName -RequiredVersion $SqlServerModuleVersion -Force -Scope CurrentUser
        } else {
            Install-Module -Name $moduleName -Force
        }
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

# Split comma-separated roles into an array
$roleArray = $DatabaseRoles -split ','

$roleSql = ""
foreach ($role in $roleArray) {
    $trimmedRole = $role.Trim()
    $roleSql += "EXEC sp_addrolemember N'$trimmedRole', N'$DisplayName';`n"
}

$sql = @"
DECLARE @username nvarchar(max) = N'$($DisplayName)';
DECLARE @clientId uniqueidentifier = '$($ClientId)';
DECLARE @sid NVARCHAR(max) = CONVERT(VARCHAR(max), CONVERT(VARBINARY(16), @clientId), 1);
DECLARE @cmd NVARCHAR(max) = N'CREATE USER [' + @username + '] WITH SID = ' + @sid + ', TYPE = E;';
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = @username)
BEGIN
    EXEC(@cmd)
END
$($roleSql)
"@

Write-Output "`nSQL:`n$($sql)`n`n"

$token = (Get-AzAccessToken -AsSecureString -ResourceUrl https://database.windows.net/).Token
$ssPtr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($token)
try {
    $serverInstance = if ($SqlServerName -like "*.database.windows.net") {  
        $SqlServerName  
    } else {  
        "$SqlServerName.database.windows.net"  
    }
    $plaintext = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($ssPtr)
    Invoke-Sqlcmd -ServerInstance $serverInstance -Database $SqlDatabaseName -AccessToken $plaintext -Query $sql -ErrorAction 'Stop'
} finally {
    # The following line ensures that sensitive data is not left in memory.
    $plainText = [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ssPtr)
}