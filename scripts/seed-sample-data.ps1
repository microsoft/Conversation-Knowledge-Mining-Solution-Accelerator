#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Seed sample conversation data into Azure AI Search and Cosmos DB.
.DESCRIPTION
    Uploads the three sample data files to Azure services after azd deployment:
      - sample_search_index_data.json       → Azure AI Search
      - sample_processed_data.json          → Cosmos DB (documents) + Azure SQL
      - sample_processed_data_key_phrases.json → Cosmos DB (key_phrases)
.EXAMPLE
    ./scripts/seed-sample-data.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Knowledge Mining — Seed Sample Data" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$projectRoot = Split-Path -Parent $PSScriptRoot

# Ensure .env exists (created by azd postprovision hook)
$envFile = Join-Path $projectRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "No .env file found. Attempting to generate from azd..." -ForegroundColor Yellow
    Push-Location $projectRoot
    azd env get-values 2>$null | ForEach-Object {
        $_ -replace '^(\w+)="(.*)"$', '$1=$2'
    } | Where-Object { $_ -match '=' -and $_ -notmatch 'WARNING' } | Set-Content -Path $envFile -Encoding utf8
    Pop-Location

    if (-not (Test-Path $envFile)) {
        Write-Host "ERROR: Could not create .env — run 'azd up' first." -ForegroundColor Red
        exit 1
    }
    Write-Host "Generated .env from azd environment." -ForegroundColor Green
}

# Check Python dependencies
Write-Host "Checking dependencies..." -ForegroundColor Yellow
$deps = @("azure-identity", "azure-search-documents", "azure-cosmos", "pyodbc")
foreach ($dep in $deps) {
    $installed = pip show $dep 2>$null
    if (-not $installed) {
        Write-Host "Installing $dep..." -ForegroundColor Yellow
        pip install $dep --quiet
    }
}

# Run the Python script
Write-Host "Running data seed script..." -ForegroundColor Yellow
Write-Host ""

python (Join-Path $PSScriptRoot "seed-sample-data.py")

if ($LASTEXITCODE -eq 0) {
    Write-Host "Sample data seeded successfully!" -ForegroundColor Green
} else {
    Write-Host "Data seeding encountered errors. See output above." -ForegroundColor Red
    exit 1
}
