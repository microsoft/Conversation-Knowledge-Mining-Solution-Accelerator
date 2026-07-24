#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build and push the backend (km-api) and frontend (km-app) container images to
    the Azure Container Registry (ACR) provisioned during `azd up`, then switch the
    App Services to run them.
.DESCRIPTION
    Uses `az acr build` so the images are built remotely inside ACR — no local
    Docker is required. Configuration is resolved from the azd environment
    (ACR_NAME, ACR_LOGIN_SERVER, API_APP_NAME, FRONTEND_APP_NAME, image names/tags,
    RESOURCE_GROUP_NAME). After pushing, each App Service is pointed at its ACR
    image and set to pull via managed identity, then restarted.
.EXAMPLE
    bash/pwsh: ./infra/scripts/build/build_and_push_images.ps1
#>

$ErrorActionPreference = "Stop"

# Repo root is three levels up from this script (infra/scripts/build -> repo root)
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path

function Get-AzdValue([string]$key) {
    $val = (azd env get-value $key 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $val -or $val -match 'ERROR|not found') { return "" }
    return $val.Trim()
}

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Build & Push Container Images" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# ── Ensure Azure CLI is authenticated ──
az account show *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Not logged in to Azure CLI. Launching 'az login'..." -ForegroundColor Yellow
    az login | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Azure CLI login failed." -ForegroundColor Red
        exit 1
    }
}

# ── Resolve configuration from azd environment ──
$resourceGroup   = Get-AzdValue "RESOURCE_GROUP_NAME"
$acrName         = Get-AzdValue "ACR_NAME"
$acrLoginServer  = Get-AzdValue "ACR_LOGIN_SERVER"
$backendImage    = Get-AzdValue "BACKEND_CONTAINER_IMAGE_NAME"
$backendTag      = Get-AzdValue "BACKEND_CONTAINER_IMAGE_TAG"
$frontendImage   = Get-AzdValue "FRONTEND_CONTAINER_IMAGE_NAME"
$frontendTag     = Get-AzdValue "FRONTEND_CONTAINER_IMAGE_TAG"
$backendApp      = Get-AzdValue "API_APP_NAME"
$frontendApp     = Get-AzdValue "FRONTEND_APP_NAME"

# ── Fallbacks / defaults ──
if (-not $acrLoginServer -and $acrName) { $acrLoginServer = "$acrName.azurecr.io" }
if (-not $backendImage)  { $backendImage  = "km-api" }
if (-not $backendTag)    { $backendTag    = "latest" }
if (-not $frontendImage) { $frontendImage = "km-app" }
if (-not $frontendTag)   { $frontendTag   = "latest" }

if (-not $acrName -or -not $backendApp -or -not $frontendApp) {
    Write-Host "ERROR: Could not resolve ACR / App Service names from azd env." -ForegroundColor Red
    Write-Host "       Ensure 'azd provision' (or 'azd up') has completed for this environment." -ForegroundColor Yellow
    Write-Host "       Required azd outputs: ACR_NAME, API_APP_NAME, FRONTEND_APP_NAME." -ForegroundColor Yellow
    exit 1
}

Write-Host "Resource Group:   $resourceGroup"
Write-Host "ACR Name:         $acrName"
Write-Host "ACR Login Server: $acrLoginServer"
Write-Host "Backend Image:    ${backendImage}:${backendTag}  -> App: $backendApp"
Write-Host "Frontend Image:   ${frontendImage}:${frontendTag}  -> App: $frontendApp"
Write-Host ""

# Build contexts and Dockerfiles
$backendContext    = Join-Path $repoRoot "src/api"
$backendDockerfile = Join-Path $repoRoot "src/api/ApiApp.Dockerfile"
$frontendContext    = Join-Path $repoRoot "src/app"
$frontendDockerfile = Join-Path $repoRoot "src/app/WebApp.Dockerfile"

function Build-Image([string]$image, [string]$tag, [string]$dockerfile, [string]$context) {
    if (-not (Test-Path $dockerfile)) {
        Write-Host "ERROR: Dockerfile not found: $dockerfile" -ForegroundColor Red
        exit 1
    }
    Write-Host "Building '${image}:${tag}' remotely in ACR '$acrName'..." -ForegroundColor Yellow
    az acr build --registry $acrName --image "${image}:${tag}" --file $dockerfile --platform linux $context
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Build of '${image}:${tag}' failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "Pushed '${image}:${tag}'." -ForegroundColor Green
}

function Update-WebAppImage([string]$appName, [string]$image, [string]$tag) {
    $fullImage = "$acrLoginServer/${image}:${tag}"
    Write-Host ""
    Write-Host "Pointing App Service '$appName' at '$fullImage'..." -ForegroundColor Yellow
    az webapp config container set `
        --name $appName `
        --resource-group $resourceGroup `
        --container-image-name $fullImage `
        --container-registry-url "https://$acrLoginServer" `
        --only-show-errors `
        --output none
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to set container image on '$appName'." -ForegroundColor Red
        exit 1
    }
    # Pull via managed identity (no admin credentials)
    az resource update `
        --resource-group $resourceGroup `
        --namespace Microsoft.Web `
        --resource-type sites `
        --name $appName `
        --set properties.siteConfig.acrUseManagedIdentityCreds=true `
        --output none 2>$null
    Write-Host "Restarting App Service '$appName'..." -ForegroundColor Yellow
    az webapp restart --name $appName --resource-group $resourceGroup --output none
    Write-Host "App Service '$appName' updated." -ForegroundColor Green
}

# ── Build & push both images ──
Build-Image $backendImage  $backendTag  $backendDockerfile  $backendContext
Build-Image $frontendImage $frontendTag $frontendDockerfile $frontendContext

# ── Switch App Services to the freshly pushed images ──
Update-WebAppImage $backendApp  $backendImage  $backendTag
Update-WebAppImage $frontendApp $frontendImage $frontendTag

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "  Images built & pushed; App Services updated." -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""
