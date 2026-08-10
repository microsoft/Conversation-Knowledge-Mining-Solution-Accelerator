#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Grant the backend API's managed identity access to Azure SQL.
.DESCRIPTION
    Reads the SQL server/database and the API managed identity from the azd
    environment, then creates a contained database user and assigns
    db_datareader / db_datawriter / db_ddladmin. Runs as the deployer (Azure CLI
    credentials); if the caller isn't the server's Entra ID admin, it temporarily
    elevates itself, runs the grant, then restores the original admin.
#>

param(
    [string]$ResourceGroupName,
    [string]$SqlServerName,
    [string]$SqlDatabaseName,
    [string]$ApiAppName,
    [string]$PrincipalId,
    # Skip the temporary Entra-admin elevation (caller must already be the SQL admin).
    [switch]$SkipAdminElevation
)

$ErrorActionPreference = "Stop"

# azd may be unavailable in AVM / non-azd deployments; guard so callers can rely on
# explicit parameters and resource-group auto-discovery instead.
$azdAvailable = [bool](Get-Command azd -ErrorAction SilentlyContinue)

function Get-AzdValue([string]$key) {
    if (-not $azdAvailable) { return "" }
    $val = (azd env get-value $key 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $val -or $val -match 'ERROR|not found') { return "" }
    return $val.Trim()
}

# ── Auto-discovery helpers: resolve names from the resource group when not
#    supplied explicitly and not available via azd (non-azd / AVM deployments). ──
function Get-DiscoveredSqlServerName([string]$rg) {
    if (-not $rg) { return "" }
    $names = (az sql server list --resource-group $rg --query "[].fullyQualifiedDomainName" -o tsv 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $names) { return "" }
    return (($names -split "`n") | Where-Object { $_ } | Select-Object -First 1).Trim()
}
function Get-DiscoveredSqlDatabaseName([string]$rg, [string]$serverShortName) {
    if (-not $rg -or -not $serverShortName) { return "" }
    $names = (az sql db list --resource-group $rg --server $serverShortName --query "[?name!='master'].name" -o tsv 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $names) { return "" }
    return (($names -split "`n") | Where-Object { $_ } | Select-Object -First 1).Trim()
}
function Get-DiscoveredWebAppName([string]$rg, [string]$prefix) {
    if (-not $rg) { return "" }
    $names = (az webapp list --resource-group $rg --query "[].name" -o tsv 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $names) { return "" }
    return (($names -split "`n") | Where-Object { $_ -like "$prefix*" } | Select-Object -First 1).Trim()
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Granting API identity SQL access" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ── Resolve configuration. When -ResourceGroupName is passed explicitly, treat it as the
#    source of truth and do NOT read azd env (a local azd default env may point elsewhere). ──
$rgProvided = [bool]$ResourceGroupName
$server      = if ($SqlServerName) { $SqlServerName } elseif ($rgProvided) { "" } else { Get-AzdValue "AZURE_SQL_SERVER" }
$database    = if ($SqlDatabaseName) { $SqlDatabaseName } elseif ($rgProvided) { "" } else { Get-AzdValue "AZURE_SQL_DATABASE" }
$apiName     = if ($ApiAppName) { $ApiAppName } elseif ($rgProvided) { "" } else { Get-AzdValue "API_APP_NAME" }
$principalId = if ($PrincipalId) { $PrincipalId } elseif ($rgProvided) { "" } else { Get-AzdValue "AZURE_API_PRINCIPAL_ID" }

$resourceGroup = if ($ResourceGroupName) { $ResourceGroupName } else { Get-AzdValue "RESOURCE_GROUP_NAME" }
$envName    = if ($rgProvided) { "" } else { Get-AzdValue "AZURE_ENV_NAME" }
$backendUri = if ($rgProvided) { "" } else { Get-AzdValue "SERVICE_BACKEND_URI" }

# Derive the app name from the backend URI (azd envs provisioned before API_APP_NAME existed).
if (-not $apiName -and $backendUri -match 'https://([^.]+)\.azurewebsites') {
    $apiName = $Matches[1]
}

# ── Auto-discovery from the resource group (used when azd is unavailable/didn't resolve a value) ──
if (-not $resourceGroup -and $envName) { $resourceGroup = "rg-$envName" }
if (-not $server)   { $server   = Get-DiscoveredSqlServerName $resourceGroup }
if (-not $apiName)  { $apiName  = Get-DiscoveredWebAppName $resourceGroup "api-" }
if (-not $database) { $database = Get-DiscoveredSqlDatabaseName $resourceGroup ($server -replace '\.database\.windows\.net$', '') }

if (-not $principalId -and $apiName -and $resourceGroup) {
    $principalId = (az webapp identity show --name $apiName --resource-group $resourceGroup --query principalId -o tsv 2>$null)
}

if (-not $server -or -not $database -or -not $apiName -or -not $principalId) {
    Write-Host "Skipping SQL role assignment — missing SQL server / database / API app name / principal ID." -ForegroundColor Yellow
    if (-not $azdAvailable -or -not $resourceGroup) {
        Write-Host "       For non-azd/AVM deployments, pass -ResourceGroupName (and optionally -SqlServerName, -SqlDatabaseName, -ApiAppName, -PrincipalId)." -ForegroundColor Yellow
    }
    exit 0
}

$accountType = (az account show --query user.type -o tsv 2>$null)
$isServicePrincipal = ($accountType -eq 'servicePrincipal')

$roles = @(
    @{ principalId = $principalId; displayName = $apiName; role = "db_datareader";  isServicePrincipal = $isServicePrincipal },
    @{ principalId = $principalId; displayName = $apiName; role = "db_datawriter";  isServicePrincipal = $isServicePrincipal },
    @{ principalId = $principalId; displayName = $apiName; role = "db_ddladmin";    isServicePrincipal = $isServicePrincipal }
)

# Write to a temp file to avoid CLI JSON quoting issues across shells
$tmp = [System.IO.Path]::GetTempFileName()
ConvertTo-Json -InputObject $roles -Depth 5 | Set-Content -Path $tmp -Encoding utf8

Write-Host "API identity : $apiName ($principalId), account type: $accountType" -ForegroundColor DarkGray
Write-Host "SQL target   : $server / $database" -ForegroundColor DarkGray

$script = Join-Path $PSScriptRoot "add_user_scripts/assign_sql_roles.py"

# ── SQL requires the caller to be the server's Entra ID admin to create contained users.
#    If the caller isn't the admin, temporarily elevate self, run the grant, then restore
#    the original admin. The app authenticates via its own contained user (not the admin
#    slot), so this swap does not affect application runtime. Skippable with -SkipAdminElevation. ──
$sqlServerShort = ($server -replace '\.database\.windows\.net$', '')
$adminSwapped = $false
$originalAdmin = $null

if (-not $SkipAdminElevation -and $resourceGroup -and $sqlServerShort) {
    # Resolve the current principal's object id (works for both users and service principals).
    $acct = (az account show -o json 2>$null) | ConvertFrom-Json
    $myObjectId = ""
    $myDisplayName = ""
    if ($acct) {
        if ($acct.user.type -eq 'servicePrincipal') {
            $myObjectId    = (az ad sp show --id $acct.user.name --query id -o tsv 2>$null)
            $myDisplayName = $acct.user.name
        } else {
            $me = (az ad signed-in-user show -o json 2>$null) | ConvertFrom-Json
            if ($me) { $myObjectId = $me.id; $myDisplayName = $me.userPrincipalName }
        }
    }
    if ($myObjectId) { $myObjectId = $myObjectId.Trim() }

    $currentAdmin = (az sql server ad-admin list --resource-group $resourceGroup --server $sqlServerShort -o json 2>$null) | ConvertFrom-Json
    $currentAdmin = $currentAdmin | Select-Object -First 1
    $adminSid = if ($currentAdmin) { $currentAdmin.sid } else { "" }

    if ($myObjectId -and $adminSid -ne $myObjectId) {
        Write-Host "Current principal is not the SQL Entra admin — elevating temporarily..." -ForegroundColor Yellow
        if ($currentAdmin) {
            az sql server ad-admin update --resource-group $resourceGroup --server $sqlServerShort --display-name $myDisplayName --object-id $myObjectId 2>$null | Out-Null
        } else {
            az sql server ad-admin create --resource-group $resourceGroup --server $sqlServerShort --display-name $myDisplayName --object-id $myObjectId 2>$null | Out-Null
        }
        if ($LASTEXITCODE -eq 0) {
            $adminSwapped = $true
            $originalAdmin = $currentAdmin
            Write-Host "Elevated. Original admin will be restored after the grant." -ForegroundColor DarkGray
        } else {
            Write-Host "WARNING: Could not set current principal as SQL Entra admin (needs SQL Server Contributor/Owner). The grant may fail." -ForegroundColor Yellow
        }
    }
}

$exit = 1
try {
    # AAD admin changes can take up to ~60s to apply to new logins; retry the grant while it propagates.
    $maxAttempts = if ($adminSwapped) { 5 } else { 1 }
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        python $script --server $server --database $database --roles-file $tmp
        $exit = $LASTEXITCODE
        if ($exit -eq 0) { break }
        if ($attempt -lt $maxAttempts) {
            Write-Host "Grant attempt $attempt failed; waiting for the admin change to propagate..." -ForegroundColor DarkYellow
            Start-Sleep -Seconds 15
        }
    }
}
finally {
    # Always restore the original admin, even if the grant threw or failed.
    if ($adminSwapped) {
        if ($originalAdmin) {
            az sql server ad-admin update --resource-group $resourceGroup --server $sqlServerShort --display-name $originalAdmin.login --object-id $originalAdmin.sid 2>$null | Out-Null
        } else {
            az sql server ad-admin delete --resource-group $resourceGroup --server $sqlServerShort 2>$null | Out-Null
        }
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Restored original SQL Entra admin." -ForegroundColor DarkGray
        } else {
            $restoreName = if ($originalAdmin) { $originalAdmin.login } else { '(none)' }
            Write-Host "WARNING: Failed to restore original SQL Entra admin '$restoreName'. Restore it manually." -ForegroundColor Red
        }
    }
}

Remove-Item -Force $tmp -ErrorAction SilentlyContinue

if ($exit -ne 0) {
    Write-Host "WARNING: SQL role assignment failed — the API may not be able to read SQL." -ForegroundColor Yellow
    exit $exit
}

Write-Host "SQL roles assigned." -ForegroundColor Green

