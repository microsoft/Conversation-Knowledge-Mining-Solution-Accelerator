#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Connect an external data source to the Knowledge Mining app.
.DESCRIPTION
    Registers a data source (Azure AI Search, Fabric) directly
    in Azure SQL. No running backend required — works right after azd up.
    The app queries your source at runtime (no data movement).
.EXAMPLE
    ./scripts/connect-data.ps1
    ./scripts/connect-data.ps1 -Type azure_search -Name "My Index" -Endpoint "https://my-search.search.windows.net" -Table "my-index"
#>

param(
    [ValidateSet("azure_search", "fabric")]
    [string]$Type,
    [string]$Name,
    [string]$Endpoint,
    [string]$Database,
    [string]$Table,
    [string]$ConnectionString
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Knowledge Mining — Connect Data Source" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$projectRoot = Split-Path -Parent $PSScriptRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pipExe = Join-Path $projectRoot ".venv\Scripts\pip.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}
if (-not (Test-Path $pipExe)) {
    $pipExe = "pip"
}

# Ensure .env exists
$envFile = Join-Path $projectRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "No .env file found. Generating from azd..." -ForegroundColor Yellow
    Push-Location $projectRoot
    azd env get-values 2>$null | ForEach-Object {
        $_ -replace '^(\w+)="(.*)"$', '$1=$2'
    } | Where-Object { $_ -match '=' -and $_ -notmatch 'WARNING' } | Set-Content -Path $envFile -Encoding utf8
    Pop-Location
}

# Check Python dependencies
$deps = @("azure-identity", "pyodbc")
foreach ($dep in $deps) {
    $installed = & $pipExe show $dep 2>$null
    if (-not $installed) {
        Write-Host "Installing $dep..." -ForegroundColor Yellow
        & $pipExe install $dep --quiet
    }
}

# Build args for the Python script
$pyArgs = @()
if ($Type)              { $pyArgs += "--type", $Type }
if ($Name)              { $pyArgs += "--name", $Name }
if ($Endpoint)          { $pyArgs += "--endpoint", $Endpoint }
if ($Database)          { $pyArgs += "--database", $Database }
if ($Table)             { $pyArgs += "--table", $Table }
if ($ConnectionString)  { $pyArgs += "--connection-string", $ConnectionString }

& $pythonExe (Join-Path $PSScriptRoot "connect-data.py") @pyArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "Data source connection failed. See output above." -ForegroundColor Red
    exit 1
}
