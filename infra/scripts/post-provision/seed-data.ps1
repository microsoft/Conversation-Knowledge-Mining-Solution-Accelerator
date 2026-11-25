#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Populate the Azure AI Search index with sample data.
.DESCRIPTION
    Uploads the sample Customer_service_data.json to the backend
    and indexes it in Azure AI Search.
.EXAMPLE
    ./infra/scripts/post-provision/seed-data.ps1
    ./infra/scripts/post-provision/seed-data.ps1 -BackendUrl https://ca-backend-xxx.azurecontainerapps.io
#>

param(
    [string]$BackendUrl = "http://localhost:8000",
    [switch]$AllowDeployedFallback
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Knowledge Mining - Seed Data" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Try to get backend URL from azd if not provided and not localhost
if ($BackendUrl -eq "http://localhost:8000") {
    if ($AllowDeployedFallback -or $env:KM_ALLOW_DEPLOYED_BACKEND_FALLBACK -eq "1") {
        $azdUrl = azd env get-value SERVICE_BACKEND_URI 2>$null
        if ($azdUrl) {
            Write-Host "Using deployed backend: $azdUrl" -ForegroundColor Yellow
            $BackendUrl = $azdUrl
        } else {
            Write-Host "ERROR: No deployed backend is configured." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Using local backend: $BackendUrl" -ForegroundColor Yellow
    }
}

function Get-ApiHeaders {
    $adminKey = $env:ADMIN_API_KEY
    if (-not $adminKey) {
        $adminKey = azd env get-value ADMIN_API_KEY 2>$null
    }
    if ($adminKey) {
        Write-Host "Using configured admin API key for script authentication" -ForegroundColor Yellow
        return @{ "X-Admin-Api-Key" = $adminKey }
    }

    Write-Host "Getting access token..." -ForegroundColor Yellow
    $clientId = $env:AZURE_AD_CLIENT_ID
    if (-not $clientId) {
        $clientId = azd env get-value AZURE_AD_CLIENT_ID 2>$null
    }
    if (-not $clientId) {
        throw "Configure AZURE_AD_CLIENT_ID or ADMIN_API_KEY. See docs/AppAuthentication.md."
    }
    $token = az account get-access-token --resource "api://$clientId" --query accessToken -o tsv 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $token -or "$token" -match '^ERROR:') {
        throw "An API access token or ADMIN_API_KEY is required. See docs/AppAuthentication.md."
    }
    return @{ Authorization = "Bearer $token" }
}

$headers = Get-ApiHeaders

Write-Host "Loading sample dataset..." -ForegroundColor Yellow
$response = Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/load-default" `
    -Method POST `
    -Headers $headers `
    -ContentType "application/json" `
    -ErrorAction Stop

Write-Host ""
Write-Host "Loaded $($response.total_loaded) documents" -ForegroundColor Green
Write-Host "Types: $($response.by_type | ConvertTo-Json -Compress)" -ForegroundColor Cyan
Write-Host ""
