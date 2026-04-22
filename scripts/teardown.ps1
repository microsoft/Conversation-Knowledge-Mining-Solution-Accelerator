#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Tear down all Azure resources for the Knowledge Mining Platform.
.DESCRIPTION
    Runs azd down to remove all provisioned resources.
.EXAMPLE
    ./scripts/teardown.ps1
    ./scripts/teardown.ps1 -Force
#>

param(
    [switch]$Force
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Red
Write-Host "  Knowledge Mining - Teardown" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Red
Write-Host ""

if (-not $Force) {
    $confirm = Read-Host "This will DELETE all Azure resources. Continue? (y/N)"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "Removing Azure resources..." -ForegroundColor Yellow
azd down --force --purge

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "All resources removed." -ForegroundColor Green
} else {
    Write-Host "Teardown encountered errors." -ForegroundColor Red
}
