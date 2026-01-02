#!/usr/bin/env pwsh

# Package React webapp for Azure App Service deployment
# This script builds the React frontend with dynamic API URL injection
# Run from workspace root OR from src/App (auto-detects location)

Write-Host "=== React App Build Started ===" -ForegroundColor Cyan

$ErrorActionPreference = "Stop"

# Detect if we're in src/App or workspace root and navigate accordingly
if (Test-Path "package.json") {
    # Already in src/App
    Write-Host "Running from src/App directory" -ForegroundColor Gray
} elseif (Test-Path "src/App/package.json") {
    # In workspace root, navigate to src/App
    Write-Host "Navigating to src/App directory" -ForegroundColor Gray
    Set-Location -Path "src/App"
} else {
    Write-Error "Cannot find React app. Run from workspace root or src/App directory."
    exit 1
}

# Clean old build folder to ensure fresh build
if (Test-Path "build") {
    Write-Host "Cleaning old build folder..." -ForegroundColor Yellow
    Remove-Item -Path "build" -Recurse -Force
}

# Get the API URL from azd environment
Write-Host "Fetching API URL from azd environment..." -ForegroundColor Yellow
$apiUrl = azd env get-value API_APP_URL

if (-not $apiUrl) {
    Write-Error "API_APP_URL not found in azd environment. Run 'azd provision' first."
    exit 1
}

Write-Host "API URL: $apiUrl" -ForegroundColor Green

# Write API URL to .env.production.local (React reads this during build)
"REACT_APP_API_BASE_URL=$apiUrl" | Out-File -FilePath ".env.production.local" -Encoding utf8
Write-Host "Created .env.production.local with API URL" -ForegroundColor Green

# Install dependencies
Write-Host "`nInstalling npm dependencies..." -ForegroundColor Cyan
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Error "npm install failed"
    exit 1
}

# Build React app
Write-Host "`nBuilding React application..." -ForegroundColor Cyan
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Error "npm run build failed"
    exit 1
}

Write-Host "`n=== React App Build Complete ===" -ForegroundColor Green
Write-Host "Built files are in ./build directory" -ForegroundColor Gray
