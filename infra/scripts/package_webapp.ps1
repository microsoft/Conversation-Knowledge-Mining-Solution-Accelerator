#!/usr/bin/env pwsh

# Package web app for Azure App Service deployment
# This script packages the application for local deployment

Write-Host "Starting web app packaging for App Service..." -ForegroundColor Cyan

$ErrorActionPreference = "Stop"

# Get the script directory and navigate to project root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir "../..")
$srcDir = Join-Path $projectRoot "src"
$distDir = Join-Path $srcDir "dist"

Write-Host "Project root: $projectRoot" -ForegroundColor Gray
Write-Host "Source directory: $srcDir" -ForegroundColor Gray
Write-Host "Dist directory: $distDir" -ForegroundColor Gray

# Clean dist directory if it exists
if (Test-Path $distDir) {
    Write-Host "Cleaning existing dist directory..." -ForegroundColor Yellow
    Remove-Item -Path $distDir -Recurse -Force
}

# Create dist directory
Write-Host "Creating dist directory..." -ForegroundColor Yellow
New-Item -Path $distDir -ItemType Directory -Force | Out-Null

# Step 1: Copy backend files
Write-Host "`nStep 1: Copying backend API files..." -ForegroundColor Cyan

# Copy Python files and backend code
$filesToCopy = @(
    "gunicorn.conf.py",
    "start.sh",
    "start.cmd",
    "asset-manifest.json",
    "manifest.json",
    "favicon-16x16.png",
    "favicon-32x32.png"
)

foreach ($file in $filesToCopy) {
    $sourcePath = Join-Path $srcDir $file
    if (Test-Path $sourcePath) {
        Write-Host "  Copying $file" -ForegroundColor Gray
        Copy-Item -Path $sourcePath -Destination $distDir -Force
    }
}

# Copy api directory (backend)
$apiSrc = Join-Path $srcDir "api"
$apiDst = Join-Path $distDir "api"
if (Test-Path $apiSrc) {
    Write-Host "  Copying api directory..." -ForegroundColor Gray
    Copy-Item -Path $apiSrc -Destination $apiDst -Recurse -Force
}

# Step 2: Build frontend
Write-Host "`nStep 2: Building frontend..." -ForegroundColor Cyan
$appDir = Join-Path $srcDir "App"

if (-not (Test-Path (Join-Path $appDir "node_modules"))) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location $appDir
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) {
            throw "npm ci failed"
        }
    } finally {
        Pop-Location
    }
}

Write-Host "Running frontend build..." -ForegroundColor Yellow
Push-Location $appDir
try {
    $env:NODE_OPTIONS = "--max_old_space_size=8192"
    npm run build
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend build failed"
    }
} finally {
    Pop-Location
    Remove-Item Env:\NODE_OPTIONS -ErrorAction SilentlyContinue
}

# Step 3: Copy App directory (frontend source)
Write-Host "`nStep 3: Copying App directory (frontend)..." -ForegroundColor Cyan
$appDst = Join-Path $distDir "App"
if (Test-Path $appDir) {
    Write-Host "  Copying App directory..." -ForegroundColor Gray
    Copy-Item -Path $appDir -Destination $appDst -Recurse -Force
}

# Verify the dist directory
$fileCount = (Get-ChildItem -Path $distDir -Recurse -File | Measure-Object).Count
$distSize = (Get-ChildItem -Path $distDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB

Write-Host "`n✓ Successfully prepared deployment package!" -ForegroundColor Green
Write-Host "  Dist location: $distDir" -ForegroundColor Cyan
Write-Host "  Total files: $fileCount" -ForegroundColor Cyan
Write-Host "  Total size: $([math]::Round($distSize, 2)) MB" -ForegroundColor Cyan

Write-Host "`nPackaging complete! azd will handle zip creation during deployment." -ForegroundColor Green
