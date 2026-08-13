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
    image and set to pull with its system-assigned managed identity, then restarted.
.EXAMPLE
    bash/pwsh: ./infra/scripts/build/build_and_push_images.ps1
#>

param(
    [string]$ResourceGroupName,
    [string]$AcrName,
    [string]$AcrLoginServer,
    [string]$ApiAppName,
    [string]$FrontendAppName,
    [string]$BackendImageName,
    [string]$BackendImageTag,
    [string]$FrontendImageName,
    [string]$FrontendImageTag
)

$ErrorActionPreference = "Stop"

# Repo root is three levels up from this script (infra/scripts/build -> repo root)
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path

# azd may be unavailable in AVM / non-azd deployments; guard so callers can rely on
# explicit parameters and resource-group auto-discovery instead.
$azdAvailable = [bool](Get-Command azd -ErrorAction SilentlyContinue)

function Get-AzdValue([string]$key) {
    if (-not $azdAvailable) { return "" }
    $val = (azd env get-value $key 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $val -or $val -match 'ERROR|not found') { return "" }
    return $val.Trim()
}

# ── Auto-discovery helpers: resolve resource names from the resource group when
#    not supplied explicitly and not available via azd (non-azd / AVM deployments). ──
function Get-DiscoveredAcrName([string]$rg) {
    if (-not $rg) { return "" }
    $names = (az acr list --resource-group $rg --query "[].name" -o tsv 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $names) { return "" }
    return (($names -split "`n") | Where-Object { $_ } | Select-Object -First 1).Trim()
}
function Get-DiscoveredWebAppName([string]$rg, [string]$prefix) {
    if (-not $rg) { return "" }
    $names = (az webapp list --resource-group $rg --query "[].name" -o tsv 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $names) { return "" }
    return (($names -split "`n") | Where-Object { $_ -like "$prefix*" } | Select-Object -First 1).Trim()
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

# ── Resolve configuration. When -ResourceGroupName is passed explicitly, treat it as
#    the source of truth and do NOT read azd env: a local azd default env may point to
#    a different deployment. Precedence: explicit param → (RG discovery | azd env). ──
$rgProvided = [bool]$ResourceGroupName
$resourceGroup   = if ($ResourceGroupName) { $ResourceGroupName } else { Get-AzdValue "RESOURCE_GROUP_NAME" }
$acrName         = if ($AcrName) { $AcrName } elseif ($rgProvided) { "" } else { Get-AzdValue "ACR_NAME" }
$acrLoginServer  = if ($AcrLoginServer) { $AcrLoginServer } elseif ($rgProvided) { "" } else { Get-AzdValue "ACR_LOGIN_SERVER" }
$backendImage    = if ($BackendImageName) { $BackendImageName } elseif ($rgProvided) { "" } else { Get-AzdValue "BACKEND_CONTAINER_IMAGE_NAME" }
$backendTag      = if ($BackendImageTag) { $BackendImageTag } elseif ($rgProvided) { "" } else { Get-AzdValue "BACKEND_CONTAINER_IMAGE_TAG" }
$frontendImage   = if ($FrontendImageName) { $FrontendImageName } elseif ($rgProvided) { "" } else { Get-AzdValue "FRONTEND_CONTAINER_IMAGE_NAME" }
$frontendTag     = if ($FrontendImageTag) { $FrontendImageTag } elseif ($rgProvided) { "" } else { Get-AzdValue "FRONTEND_CONTAINER_IMAGE_TAG" }
$backendApp      = if ($ApiAppName) { $ApiAppName } elseif ($rgProvided) { "" } else { Get-AzdValue "API_APP_NAME" }
$frontendApp     = if ($FrontendAppName) { $FrontendAppName } elseif ($rgProvided) { "" } else { Get-AzdValue "FRONTEND_APP_NAME" }

# ── Auto-discovery from the resource group (when azd is bypassed/unavailable or didn't resolve a value) ──
if (-not $acrName)     { $acrName     = Get-DiscoveredAcrName $resourceGroup }
if (-not $backendApp)  { $backendApp  = Get-DiscoveredWebAppName $resourceGroup "api-" }
if (-not $frontendApp) { $frontendApp = Get-DiscoveredWebAppName $resourceGroup "app-" }

# ── Fallbacks / defaults ──
if (-not $acrLoginServer -and $acrName) { $acrLoginServer = "$acrName.azurecr.io" }
if (-not $backendImage)  { $backendImage  = "km-api" }
if (-not $backendTag)    { $backendTag    = "latest" }
if (-not $frontendImage) { $frontendImage = "km-app" }
if (-not $frontendTag)   { $frontendTag   = "latest" }

if (-not $acrName -or -not $backendApp -or -not $frontendApp) {
    Write-Host "ERROR: Could not resolve ACR / App Service names." -ForegroundColor Red
    if ($azdAvailable) {
        Write-Host "       Ensure 'azd provision' (or 'azd up') has completed for this environment," -ForegroundColor Yellow
        Write-Host "       or pass -AcrName, -ApiAppName and -FrontendAppName explicitly." -ForegroundColor Yellow
    } else {
        Write-Host "       Auto-discovery from -ResourceGroupName '$resourceGroup' did not find them (expects a single ACR and" -ForegroundColor Yellow
        Write-Host "       App Services named 'api-*'/'app-*'). Pass -AcrName, -ApiAppName and -FrontendAppName explicitly." -ForegroundColor Yellow
    }
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
    # App Service pulls with its system-assigned managed identity (AcrPull granted in Bicep).
    # Enable managed-identity pull first so the container config below needs no admin creds.
    $webappId = (az webapp show --name $appName --resource-group $resourceGroup --query id -o tsv)
    az resource update --ids "$webappId/config/web" `
        --set properties.acrUseManagedIdentityCreds=true `
        --output none 2>$null
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
    Write-Host "Restarting App Service '$appName'..." -ForegroundColor Yellow
    az webapp restart --name $appName --resource-group $resourceGroup --output none
    Write-Host "App Service '$appName' updated." -ForegroundColor Green
}

function Wait-ForAppReady([string]$appName, [string]$healthPath = "/", [int]$timeoutSeconds = 300) {
    $url = "https://$appName.azurewebsites.net$healthPath"
    Write-Host "Waiting for '$appName' to become ready..." -ForegroundColor Yellow
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $url -Method GET -TimeoutSec 10 -SkipHttpErrorCheck
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host "'$appName' is ready." -ForegroundColor Green
                return $true
            }
        } catch {
            # Ignore transient errors (connection refused, 503, timeouts) while cold-starting.
        }
        Start-Sleep -Seconds 5
    }
    Write-Host "WARNING: '$appName' did not become ready within ${timeoutSeconds}s — continuing anyway." -ForegroundColor Yellow
    return $false
}

# ── Build & push both images ──
Build-Image $backendImage  $backendTag  $backendDockerfile  $backendContext
Build-Image $frontendImage $frontendTag $frontendDockerfile $frontendContext

# ── Switch App Services to the freshly pushed images ──
Update-WebAppImage $backendApp  $backendImage  $backendTag
Update-WebAppImage $frontendApp $frontendImage $frontendTag

# ── Wait for both apps to finish cold-starting on the new image
Write-Host ""
Wait-ForAppReady $backendApp "/api/health" | Out-Null
Wait-ForAppReady $frontendApp "/" | Out-Null

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "  Images built & pushed; App Services updated." -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""
