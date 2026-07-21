#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Grant the backend API's managed identity access to Azure SQL.
.DESCRIPTION
    Reads the SQL server/database and the API managed identity from the azd
    environment, then creates a contained database user and assigns
    db_datareader / db_datawriter / db_ddladmin. Runs as the deployer (Azure CLI
    credentials), who must be the SQL Azure AD admin.
#>

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Granting API identity SQL access" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$server      = (azd env get-value AZURE_SQL_SERVER 2>$null)      | Where-Object { $_ -notmatch 'ERROR' }
$database    = (azd env get-value AZURE_SQL_DATABASE 2>$null)     | Where-Object { $_ -notmatch 'ERROR' }
$apiName     = (azd env get-value API_APP_NAME 2>$null)           | Where-Object { $_ -notmatch 'ERROR' }
$principalId = (azd env get-value AZURE_API_PRINCIPAL_ID 2>$null) | Where-Object { $_ -notmatch 'ERROR' }

$envName  = (azd env get-value AZURE_ENV_NAME 2>$null)        | Where-Object { $_ -notmatch 'ERROR' }
$backendUri = (azd env get-value SERVICE_BACKEND_URI 2>$null) | Where-Object { $_ -notmatch 'ERROR' }

# Fallbacks for environments provisioned before the API_APP_NAME / AZURE_API_PRINCIPAL_ID
# outputs were added: derive the app name from the backend URI and look up the
# principal ID with the Azure CLI.
if (-not $apiName -and $backendUri -match 'https://([^.]+)\.azurewebsites') {
    $apiName = $Matches[1]
}
if (-not $principalId -and $apiName -and $envName) {
    $principalId = (az webapp identity show --name $apiName --resource-group "rg-$envName" --query principalId -o tsv 2>$null)
}

if (-not $server -or -not $database -or -not $apiName -or -not $principalId) {
    Write-Host "Skipping SQL role assignment — missing AZURE_SQL_SERVER / AZURE_SQL_DATABASE / API_APP_NAME / AZURE_API_PRINCIPAL_ID." -ForegroundColor Yellow
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
python $script --server $server --database $database --roles-file $tmp
$exit = $LASTEXITCODE

Remove-Item -Force $tmp -ErrorAction SilentlyContinue

if ($exit -ne 0) {
    Write-Host "WARNING: SQL role assignment failed — the API may not be able to read SQL." -ForegroundColor Yellow
    exit $exit
}

Write-Host "SQL roles assigned." -ForegroundColor Green

