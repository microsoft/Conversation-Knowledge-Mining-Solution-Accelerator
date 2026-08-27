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
    ./infra/scripts/post-provision/setup-agent.ps1 -Scenario contact-center
#>

param(
    [string]$Scenario,
    [string]$ResourceGroupName,
    [string]$ApiAppName
)

# azd may be unavailable in AVM / non-azd deployments; guard so callers can rely on
# explicit parameters and resource-group auto-discovery instead.
$azdAvailable = [bool](Get-Command azd -ErrorAction SilentlyContinue)

function Get-AzdEnvValue {
    param([string]$Name)
    if (-not $azdAvailable) { return "" }
    $value = azd env get-value $Name 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $value) { return "" }
    $text = ($value | Out-String).Trim()
    if ($text -match '^ERROR:') { return "" }
    return $text
}

function Get-DiscoveredWebAppName {
    param([string]$Rg, [string]$Prefix)
    if (-not $Rg) { return "" }
    $names = (az webapp list --resource-group $Rg --query "[].name" -o tsv 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $names) { return "" }
    return (($names -split "`n") | Where-Object { $_ -like "$Prefix*" } | Select-Object -First 1).Trim()
}

# For non-azd / AVM deployments (no local .env), hydrate this process's environment
# from the deployed API App Service settings so create_agent.py can read them.
# -Overwrite makes the RG the source of truth: it replaces stale session/.env values
# (e.g. leftovers from a previous run against a different environment).
function Import-AppSettingsToEnv {
    param([string]$AppName, [string]$Rg, [switch]$Overwrite)
    if (-not $AppName -or -not $Rg) { return }
    $json = (az webapp config appsettings list --name $AppName --resource-group $Rg -o json 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $json) { return }
    try { $settings = $json | ConvertFrom-Json } catch { return }
    foreach ($s in $settings) {
        if ($s.name -and ($Overwrite -or -not (Test-Path "Env:$($s.name)"))) {
            Set-Item -Path "Env:$($s.name)" -Value $s.value
        }
    }
}

# ── Resolve resource group / API app. When -ResourceGroupName is passed explicitly, treat
#    it as the source of truth and do NOT read azd env (which may point to a different env). ──
$rgProvided = [bool]$ResourceGroupName
$resourceGroup = if ($ResourceGroupName) { $ResourceGroupName } else { Get-AzdEnvValue -Name "RESOURCE_GROUP_NAME" }
if (-not $resourceGroup) { $resourceGroup = Get-AzdEnvValue -Name "AZURE_RESOURCE_GROUP" }
$apiAppName = if ($ApiAppName) { $ApiAppName } elseif ($rgProvided) { Get-DiscoveredWebAppName $resourceGroup "api-" } else { Get-AzdEnvValue -Name "API_APP_NAME" }
if (-not $apiAppName) { $apiAppName = Get-DiscoveredWebAppName $resourceGroup "api-" }

# Explicit RG: hydrate config from that deployment's API app so a stale local .env
# (from a different azd environment) cannot leak into agent creation. Overwrite so the
# RG wins over any pre-existing session env var or stale .env value.
if ($rgProvided) { Import-AppSettingsToEnv -AppName $apiAppName -Rg $resourceGroup -Overwrite }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Knowledge Mining - Agent Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$envFile = Join-Path $PSScriptRoot ".." ".." ".." ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "WARNING: .env file not found. Resolving configuration from the deployment..." -ForegroundColor Yellow

    $endpoint = Get-AzdEnvValue -Name "AZURE_AI_AGENT_ENDPOINT"
    if (-not $endpoint) {
        # Non-azd / AVM deployment: hydrate from the deployed API App Service settings.
        Import-AppSettingsToEnv -AppName $apiAppName -Rg $resourceGroup
        $endpoint = $env:AZURE_AI_AGENT_ENDPOINT
    }
    if (-not $endpoint) {
        Write-Host "ERROR: AZURE_AI_AGENT_ENDPOINT not set." -ForegroundColor Red
        Write-Host "Set it in .env, run 'azd env set AZURE_AI_AGENT_ENDPOINT <value>', or pass -ResourceGroupName so it can be read from the deployed API app." -ForegroundColor Yellow
        exit 1
    }
}

# Resolve the Python interpreter — prefer the project virtual environment, which
# has the pinned SDK versions (requirements.txt). Fall back to PATH python.
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot ".." ".." "..")).Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) { $pythonExe = "python" }

Write-Host "Generating scenario-based agent prompt..." -ForegroundColor Yellow
$genArgs = @()
if ($Scenario) { $genArgs += @("--scenario", $Scenario) }
& $pythonExe (Join-Path $PSScriptRoot "generate_agent_prompt.py") @genArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "Prompt generation failed." -ForegroundColor Red
    exit 1
}

Write-Host "Creating agents..." -ForegroundColor Yellow
$createArgs = @()
if ($Scenario) { $createArgs += @("--scenario", $Scenario) }
& $pythonExe (Join-Path $PSScriptRoot "create_agent.py") @createArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Agent created successfully!" -ForegroundColor Green
    Write-Host ""

    # Push the freshly created agent settings to the API App Service so the
    # running backend picks up AGENT_NAME_CHAT / AGENT_NAME_TITLE / USE_SQL.
    # $resourceGroup and $apiAppName were resolved above (param → azd env → RG discovery).
    $agentNameChat  = if ($rgProvided) { "" } else { Get-AzdEnvValue -Name "AGENT_NAME_CHAT" }
    $agentNameTitle = if ($rgProvided) { "" } else { Get-AzdEnvValue -Name "AGENT_NAME_TITLE" }
    $useSql         = if ($rgProvided) { "" } else { Get-AzdEnvValue -Name "USE_SQL" }
    $dataSourceType = if ($rgProvided) { "" } else { Get-AzdEnvValue -Name "DATA_SOURCE_TYPE" }

    # Fallback (non-azd / AVM): read what create_agent.py just wrote to agent_ids.json.
    if (-not $agentNameChat -or -not $agentNameTitle) {
        $agentIdsPath = Join-Path $projectRoot "data" "config" "agent_ids.json"
        if (Test-Path $agentIdsPath) {
            try {
                $agentIds = Get-Content $agentIdsPath -Raw | ConvertFrom-Json
                if (-not $agentNameChat)  { $agentNameChat  = $agentIds.chat_agent_name }
                if (-not $agentNameTitle) { $agentNameTitle = $agentIds.title_agent_name }
                if (-not $useSql)         { $useSql         = [string]$agentIds.use_sql }
                if (-not $dataSourceType) { $dataSourceType = $agentIds.data_source_type }
            } catch {}
        }
    }

    if ($apiAppName -and $resourceGroup) {
        Write-Host "Updating API App Service '$apiAppName' agent settings..." -ForegroundColor Yellow
        # Only include settings that actually have a value. USE_SQL in particular is parsed as
        # a Pydantic bool by the API (src/api/config.py) — pushing "USE_SQL=" (empty) still
        # fails validation at startup just like the literal "ERROR: ..." text Get-AzdEnvValue
        # now filters out, so an empty/invalid value must be omitted entirely rather than sent.
        $settingsArgs = @()
        if ($agentNameChat)  { $settingsArgs += "AGENT_NAME_CHAT=$agentNameChat" }
        if ($agentNameTitle) { $settingsArgs += "AGENT_NAME_TITLE=$agentNameTitle" }
        if ($useSql -match '^(?i:true|false)$') { $settingsArgs += "USE_SQL=$useSql" }
        if ($dataSourceType) { $settingsArgs += "DATA_SOURCE_TYPE=$dataSourceType" }

        if ($settingsArgs.Count -eq 0) {
            Write-Host "  [SKIP] No agent settings resolved; nothing to sync" -ForegroundColor Yellow
        } else {
            az webapp config appsettings set `
                --name $apiAppName `
                --resource-group $resourceGroup `
                --settings $settingsArgs `
                --output none
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  [OK] App Service settings updated" -ForegroundColor Green
            } else {
                Write-Host "  [WARN] Failed to update App Service settings" -ForegroundColor Yellow
                $global:LASTEXITCODE = 0
            }
        }
    } else {
        Write-Host "  [SKIP] Could not resolve API app / resource group; skipping App Service settings sync" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Test it:" -ForegroundColor Yellow
    Write-Host "  python infra/scripts/utilities/test_agent.py"
    Write-Host "  python infra/scripts/utilities/test_agent.py -v  (verbose mode)"
    Write-Host ""
} else {
    Write-Host "Agent creation failed." -ForegroundColor Red
    exit 1
}
