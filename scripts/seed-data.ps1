#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Populate the Azure AI Search index with sample data.
.DESCRIPTION
    Uploads the sample Customer_service_data.json to the backend
    and indexes it in Azure AI Search.
.EXAMPLE
    ./scripts/seed-data.ps1
    ./scripts/seed-data.ps1 -BackendUrl https://ca-backend-xxx.azurecontainerapps.io
#>

param(
    [string]$BackendUrl = "http://localhost:8000"
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Knowledge Mining - Seed Data" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Try to get backend URL from azd if not provided and not localhost
if ($BackendUrl -eq "http://localhost:8000") {
    $azdUrl = azd env get-value SERVICE_BACKEND_URI 2>$null
    if ($azdUrl) {
        Write-Host "Using deployed backend: $azdUrl" -ForegroundColor Yellow
        $BackendUrl = $azdUrl
    } else {
        Write-Host "Using local backend: $BackendUrl" -ForegroundColor Yellow
    }
}

# Get token
Write-Host "Getting access token..." -ForegroundColor Yellow
$token = az account get-access-token --resource "api://$(azd env get-value AZURE_AD_CLIENT_ID 2>$null)" --query accessToken -o tsv 2>$null
if (-not $token) {
    $token = "test"
    Write-Host "Using test token (local dev)" -ForegroundColor Yellow
}

# Load default dataset
Write-Host "Loading sample dataset..." -ForegroundColor Yellow
$response = Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/load-default" `
    -Method POST `
    -Headers @{ Authorization = "Bearer $token" } `
    -ContentType "application/json" `
    -ErrorAction Stop

Write-Host ""
Write-Host "Loaded $($response.total_loaded) documents" -ForegroundColor Green
Write-Host "Types: $($response.by_type | ConvertTo-Json -Compress)" -ForegroundColor Cyan
Write-Host ""
