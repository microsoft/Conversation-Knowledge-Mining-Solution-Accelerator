#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build and push Docker images to Azure Container Registry.
.DESCRIPTION
    Reads ACR hostname from azd env (BACKEND_CONTAINER_REGISTRY / FRONTEND_CONTAINER_REGISTRY).
    Builds backend (km-api) and frontend (km-app) images and pushes them to ACR.
    The frontend image is built with REACT_APP_API_BASE_URL baked in.
#>

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Building & Pushing Docker Images" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Read env values
$backendRegistry = (azd env get-value BACKEND_CONTAINER_REGISTRY 2>$null) | Where-Object { $_ -notmatch 'ERROR' }
$frontendRegistry = (azd env get-value FRONTEND_CONTAINER_REGISTRY 2>$null) | Where-Object { $_ -notmatch 'ERROR' }
$backendTag = (azd env get-value BACKEND_IMAGE_TAG 2>$null) | Where-Object { $_ -notmatch 'ERROR' }
$frontendTag = (azd env get-value FRONTEND_IMAGE_TAG 2>$null) | Where-Object { $_ -notmatch 'ERROR' }
$backendUri = (azd env get-value SERVICE_BACKEND_URI 2>$null) | Where-Object { $_ -notmatch 'ERROR' }

if (-not $backendTag) { $backendTag = "latest" }
if (-not $frontendTag) { $frontendTag = "latest" }

if (-not $backendRegistry -or -not $frontendRegistry) {
    Write-Host "No container registry configured — skipping image build." -ForegroundColor Yellow
    Write-Host "Set BACKEND_CONTAINER_REGISTRY and FRONTEND_CONTAINER_REGISTRY in azd env to enable." -ForegroundColor Yellow
    exit 0
}

$acrName = $backendRegistry.Split('.')[0]

# Log in to ACR
Write-Host "Logging in to ACR: $backendRegistry" -ForegroundColor Yellow
az acr login --name $acrName
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to log in to ACR." -ForegroundColor Red
    exit 1
}

# Build backend image
$backendImage = "$backendRegistry/km-api:$backendTag"
Write-Host ""
Write-Host "Building backend image: $backendImage" -ForegroundColor Yellow
docker build -t $backendImage -f src/api/Dockerfile .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backend image build failed." -ForegroundColor Red
    exit 1
}

Write-Host "Pushing backend image..." -ForegroundColor Yellow
docker push $backendImage
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backend image push failed." -ForegroundColor Red
    exit 1
}
Write-Host "Backend image pushed." -ForegroundColor Green

# Build frontend image
$frontendImage = "$frontendRegistry/km-app:$frontendTag"
Write-Host ""
Write-Host "Building frontend image: $frontendImage" -ForegroundColor Yellow

$buildArgs = @()
if ($backendUri) {
    $apiUrl = "$backendUri/api"
    $buildArgs = @("--build-arg", "REACT_APP_API_BASE_URL=$apiUrl")
    Write-Host "  API URL: $apiUrl" -ForegroundColor DarkGray
}

docker build $buildArgs -t $frontendImage -f src/app/Dockerfile src/app
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Frontend image build failed." -ForegroundColor Red
    exit 1
}

Write-Host "Pushing frontend image..." -ForegroundColor Yellow
docker push $frontendImage
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Frontend image push failed." -ForegroundColor Red
    exit 1
}
Write-Host "Frontend image pushed." -ForegroundColor Green

# Restart webapps to pull new images
$envName = (azd env get-value AZURE_ENV_NAME 2>$null) | Where-Object { $_ -notmatch 'ERROR' }
if ($envName) {
    $rgName = "rg-$envName"
    $resourceToken = (azd env get-value SERVICE_BACKEND_URI 2>$null) | Where-Object { $_ -notmatch 'ERROR' }
    # Extract resource token from backend URI (e.g. https://api-XXXX.azurewebsites.net -> XXXX)
    if ($resourceToken -match 'api-([^.]+)\.azurewebsites') {
        $token = $Matches[1]
        $apiApp = "api-$token"
        $webApp = "app-$token"

        Write-Host ""
        Write-Host "Restarting webapps..." -ForegroundColor Yellow
        az webapp restart --name $apiApp --resource-group $rgName 2>$null
        az webapp restart --name $webApp --resource-group $rgName 2>$null
        Write-Host "Webapps restarted." -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "All images built, pushed, and deployed." -ForegroundColor Green
Write-Host ""
