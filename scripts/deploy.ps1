#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy the Knowledge Mining Platform to Azure using azd.
.DESCRIPTION
    This script provisions all Azure resources, builds Docker images,
    deploys to Container Apps, and assigns RBAC roles.
.EXAMPLE
    ./scripts/deploy.ps1
    ./scripts/deploy.ps1 -Location eastus2
#>

param(
    [string]$EnvironmentName = "",
    [string]$Location = "",
    [string]$Subscription = ""
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
    Write-Host "  Deployment Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Frontend: $(azd env get-value SERVICE_FRONTEND_URI)" -ForegroundColor Cyan
    Write-Host "Backend:  $(azd env get-value SERVICE_BACKEND_URI)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Open the frontend URL in your browser"
    Write-Host "  2. Upload documents or connect an existing index"
    Write-Host "  3. (Optional) Run: python scripts/create_agent.py"
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Deployment failed. Check the errors above." -ForegroundColor Red
    exit 1
}
