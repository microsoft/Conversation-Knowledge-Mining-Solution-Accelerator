#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy the Knowledge Mining Platform to Azure using azd.
.DESCRIPTION
    This script provisions all Azure resources, builds Docker images,
    deploys to Container Apps, and assigns RBAC roles.
.EXAMPLE
    ./infra/scripts/deploy.ps1
    ./infra/scripts/deploy.ps1 -Location eastus2
#>

param(
    [string]$EnvironmentName = "",
    [string]$Location = "",
    [string]$Subscription = "",

    [ValidateSet("contact-center", "mortgage-application", "telecom-analysis")]
    [string]$Scenario = "",

    [ValidateSet("azure_search", "fabric", "sql", "synapse")]
    [string]$ExternalSource = "",

    [switch]$SkipDataSetup
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Knowledge Mining Platform - Deploy" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$azdVersion = az version --query '"azure-dev"' -o tsv 2>$null
if (-not $azdVersion) {
    Write-Host "ERROR: Azure Developer CLI (azd) is required." -ForegroundColor Red
    Write-Host "Install: https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd" -ForegroundColor Yellow
    exit 1
}
Write-Host "azd version: $azdVersion" -ForegroundColor Green

$account = azd auth login --check-status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Logging in to Azure..." -ForegroundColor Yellow
    azd auth login
}

if ($EnvironmentName) {
    azd env new $EnvironmentName
}

if ($Location) {
    azd env set AZURE_LOCATION $Location
}

if ($Subscription) {
    azd env set AZURE_SUBSCRIPTION_ID $Subscription
}

Write-Host ""
Write-Host "Provisioning Azure resources..." -ForegroundColor Yellow
azd up

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Infrastructure Deployed!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Frontend: $(azd env get-value SERVICE_FRONTEND_URI)" -ForegroundColor Cyan
    Write-Host "Backend:  $(azd env get-value SERVICE_BACKEND_URI)" -ForegroundColor Cyan
    Write-Host ""

    # Post-deploy: agent setup + data setup happen automatically via azd postprovision hook.
    # If running this script directly (outside azd), run them now:
    $hookRan = $env:AZD_HOOK_NAME
    if (-not $hookRan) {
        Write-Host "Running post-deployment setup..." -ForegroundColor Yellow
        Write-Host ""

        # Agent setup
        & (Join-Path $PSScriptRoot "setup-agent.ps1")

        # Data setup — use param if provided, otherwise prompt
        if (-not $SkipDataSetup) {
            $setupScript = Join-Path $PSScriptRoot ".." ".." "scripts" "setup-data.ps1"
            if ($Scenario) {
                & $setupScript -Scenario $Scenario
            } elseif ($ExternalSource) {
                & $setupScript -ExternalSource $ExternalSource
            } else {
                & $setupScript
            }
        }
    }

    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Deployment failed. Check the errors above." -ForegroundColor Red
    exit 1
}
