#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Set up the Azure AI Foundry agent after deployment.
.DESCRIPTION
    Creates the KnowledgeMiningAgent in Azure AI Foundry with
    Azure AI Search as a tool. Run after azd up.
.PARAMETER Scenario
    Scenario key from data/config/scenarios.json used to generate the agent prompt.
.EXAMPLE
    ./scripts/setup-agent.ps1 -Scenario contact-center
#>

param(
    [string]$Scenario
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Knowledge Mining - Agent Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$envFile = Join-Path $PSScriptRoot ".." ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "WARNING: .env file not found. Trying azd env values..." -ForegroundColor Yellow

    # Try to get values from azd
    $endpoint = azd env get-value AZURE_AI_AGENT_ENDPOINT 2>$null
    if (-not $endpoint) {
        Write-Host "ERROR: AZURE_AI_AGENT_ENDPOINT not set." -ForegroundColor Red
        Write-Host "Set it in .env or run: azd env set AZURE_AI_AGENT_ENDPOINT <value>" -ForegroundColor Yellow
        exit 1
    }
}

# Activate venv if available
$venvPath = Join-Path $PSScriptRoot ".." "venv" "Scripts" "Activate.ps1"
if (Test-Path $venvPath) {
    & $venvPath
}

Write-Host "Generating scenario-based agent prompt..." -ForegroundColor Yellow
$genArgs = @()
if ($Scenario) { $genArgs += @("--scenario", $Scenario) }
python (Join-Path $PSScriptRoot "generate_agent_prompt.py") @genArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "Prompt generation failed." -ForegroundColor Red
    exit 1
}

Write-Host "Creating agents..." -ForegroundColor Yellow
$createArgs = @()
if ($Scenario) { $createArgs += @("--scenario", $Scenario) }
python (Join-Path $PSScriptRoot "create_agent.py") @createArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Agent created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Test it:" -ForegroundColor Yellow
    Write-Host "  python infra/scripts/test_agent.py"
    Write-Host "  python infra/scripts/test_agent.py -v  (verbose mode)"
    Write-Host ""
} else {
    Write-Host "Agent creation failed." -ForegroundColor Red
    exit 1
}
