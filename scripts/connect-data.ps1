#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Connect an external data source to the Knowledge Mining app.
.DESCRIPTION
    Registers a data source (Azure AI Search, Fabric) directly
    in Azure SQL. No running backend required — works right after azd up.
    The app queries your source at runtime (no data movement).
.EXAMPLE
    ./scripts/connect-data.ps1
    ./scripts/connect-data.ps1 -Type azure_search -Name "My Index" -Endpoint "https://my-search.search.windows.net" -Table "my-index"
#>

param(
    [ValidateSet("azure_search", "fabric")]
    [string]$Type,
    [string]$Name,
    [string]$Endpoint,
    [string]$Database,
    [string]$Table,
    [string]$ConnectionString,
    [string]$WorkspaceId
)

$ErrorActionPreference = "Stop"

function Get-AzdEnvValue {
    param([string]$Name)
    $value = azd env get-value $Name 2>$null
    if (-not $value) { return "" }
    if ($value -is [string] -and $value.StartsWith("ERROR:")) { return "" }
    return "$value".Trim()
}

function Sync-AgentSettingsToApi {
    param([string]$ProjectRoot)

    $apiAppName = Get-AzdEnvValue -Name "API_APP_NAME"
    $resourceGroup = Get-AzdEnvValue -Name "RESOURCE_GROUP_NAME"
    if (-not $resourceGroup) {
        $resourceGroup = Get-AzdEnvValue -Name "AZURE_RESOURCE_GROUP"
    }

    $agentNameChat = Get-AzdEnvValue -Name "AGENT_NAME_CHAT"
    $agentNameTitle = Get-AzdEnvValue -Name "AGENT_NAME_TITLE"
    $useSql = Get-AzdEnvValue -Name "USE_SQL"
    $dataSourceType = Get-AzdEnvValue -Name "DATA_SOURCE_TYPE"

    if (-not $agentNameChat -or -not $agentNameTitle) {
        # Fall back to .env if azd env values are not available.
        $envFilePath = Join-Path $ProjectRoot ".env"
        if (Test-Path $envFilePath) {
            if (-not $agentNameChat) {
                $agentNameChat = (Get-Content $envFilePath | Where-Object { $_ -match '^AGENT_NAME_CHAT=' }) -replace '^AGENT_NAME_CHAT=', ''
            }
            if (-not $agentNameTitle) {
                $agentNameTitle = (Get-Content $envFilePath | Where-Object { $_ -match '^AGENT_NAME_TITLE=' }) -replace '^AGENT_NAME_TITLE=', ''
            }
            if (-not $useSql) {
                $useSql = (Get-Content $envFilePath | Where-Object { $_ -match '^USE_SQL=' }) -replace '^USE_SQL=', ''
            }
            if (-not $dataSourceType) {
                $dataSourceType = (Get-Content $envFilePath | Where-Object { $_ -match '^DATA_SOURCE_TYPE=' }) -replace '^DATA_SOURCE_TYPE=', ''
            }
        }
    }

    if (-not $apiAppName -or -not $resourceGroup) {
        Write-Host "  [SKIP] API_APP_NAME / RESOURCE_GROUP_NAME not found in azd env" -ForegroundColor Yellow
        return
    }
    if (-not $agentNameChat -or -not $agentNameTitle) {
        Write-Host "  [WARN] AGENT_NAME_CHAT / AGENT_NAME_TITLE not found; skipping App Service settings sync" -ForegroundColor Yellow
        return
    }

    Write-Host "Updating API App Service '$apiAppName' agent settings..." -ForegroundColor Yellow
    az webapp config appsettings set `
        --name $apiAppName `
        --resource-group $resourceGroup `
        --settings "AGENT_NAME_CHAT=$agentNameChat" "AGENT_NAME_TITLE=$agentNameTitle" "USE_SQL=$useSql" "DATA_SOURCE_TYPE=$dataSourceType" `
        --output none

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] App Service settings updated" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Failed to update App Service settings" -ForegroundColor Yellow
        $global:LASTEXITCODE = 0
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Knowledge Mining — Connect Data Source" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$projectRoot = Split-Path -Parent $PSScriptRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pipExe = Join-Path $projectRoot ".venv\Scripts\pip.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}
if (-not (Test-Path $pipExe)) {
    $pipExe = "pip"
}

# Ensure .env exists
$envFile = Join-Path $projectRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "No .env file found. Generating from azd..." -ForegroundColor Yellow
    Push-Location $projectRoot
    azd env get-values 2>$null | ForEach-Object {
        $_ -replace '^(\w+)="(.*)"$', '$1=$2'
    } | Where-Object { $_ -match '=' -and $_ -notmatch 'WARNING' } | Set-Content -Path $envFile -Encoding utf8
    Pop-Location
}

# Check Python dependencies
$deps = @("azure-identity", "pyodbc")
foreach ($dep in $deps) {
    $installed = & $pipExe show $dep 2>$null
    if (-not $installed) {
        Write-Host "Installing $dep..." -ForegroundColor Yellow
        & $pipExe install $dep --quiet
    }
}

# Build args for the Python script
$pyArgs = @()
if ($Type)              { $pyArgs += "--type", $Type }
if ($Name)              { $pyArgs += "--name", $Name }
if ($Endpoint)          { $pyArgs += "--endpoint", $Endpoint }
if ($Database)          { $pyArgs += "--database", $Database }
if ($Table)             { $pyArgs += "--table", $Table }
if ($ConnectionString)  { $pyArgs += "--connection-string", $ConnectionString }
if ($WorkspaceId)       { $pyArgs += "--workspace-id", $WorkspaceId }

& $pythonExe (Join-Path $PSScriptRoot "connect-data.py") @pyArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "Data source connection failed. See output above." -ForegroundColor Red
    exit 1
}

# Auto-create agents if this is an Azure AI Search connection
$resolvedSourceType = $Type
if (-not $resolvedSourceType) {
    # Try to read the source type from the temp file written by connect-data.py
    $lastConnPath = Join-Path $projectRoot ".last_byod_connection.json"
    if (Test-Path $lastConnPath) {
        $lastConn = Get-Content $lastConnPath -Raw | ConvertFrom-Json
        $resolvedSourceType = $lastConn.source_type
    }
}

if ($resolvedSourceType -eq "azure_search") {
    # Read the actual index name from the temp file written by connect-data.py
    $lastConnPath = Join-Path $projectRoot ".last_byod_connection.json"
    $resolvedTable = $Table
    $resolvedName  = $Name
    $resolvedSearchConnection = ""
    if (Test-Path $lastConnPath) {
        $lastConn = Get-Content $lastConnPath -Raw | ConvertFrom-Json
        if (-not $resolvedTable) { $resolvedTable = $lastConn.table_or_query }
        if (-not $resolvedName)  { $resolvedName  = $lastConn.name }
        $resolvedSearchConnection = $lastConn.search_connection
        Remove-Item $lastConnPath -ErrorAction SilentlyContinue
    }
    if (-not $resolvedTable) { $resolvedTable = "knowledge-mining-index" }
    if (-not $resolvedName)  { $resolvedName  = "byod" }

    # Agent names: alphanumeric + hyphens only, start/end alphanumeric, max 63 chars
    $agentName = ("agent-" + ($resolvedName -replace '[^a-zA-Z0-9]', '-').ToLower().Trim('-'))
    $agentName = $agentName -replace '-{2,}', '-'   # collapse consecutive hyphens
    $agentName = $agentName.Substring(0, [Math]::Min($agentName.Length, 63)).TrimEnd('-')

    # Read AZURE_AI_AGENT_ENDPOINT
    $agentEndpoint = azd env get-value AZURE_AI_AGENT_ENDPOINT 2>$null
    if (-not $agentEndpoint) {
        $envFile = Join-Path $projectRoot ".env"
        if (Test-Path $envFile) {
            $agentEndpoint = (Get-Content $envFile | Where-Object { $_ -match '^AZURE_AI_AGENT_ENDPOINT=' }) -replace '^AZURE_AI_AGENT_ENDPOINT=', ''
        }
    }

    if ($agentEndpoint) {
        Write-Host ""
        Write-Host "Creating AI agents for conversational access..." -ForegroundColor Cyan

        $agentArgs = @(
            (Join-Path $PSScriptRoot "create_agent.py"),
            "--scenario", "azure_search_byod",
            "--index-name", $resolvedTable,
            "--agent-name", $agentName
        )
        if ($resolvedSearchConnection) { $agentArgs += "--connection-name", $resolvedSearchConnection }

        & $pythonExe @agentArgs

        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Agents created and ready." -ForegroundColor Green
            Sync-AgentSettingsToApi -ProjectRoot $projectRoot
        } else {
            Write-Host "[WARN] Agent creation encountered errors. You can retry:" -ForegroundColor Yellow
            Write-Host "       python scripts/create_agent.py --scenario azure_search_byod --index-name $resolvedTable --agent-name $agentName" -ForegroundColor DarkGray
        }
    } else {
        Write-Host ""
        Write-Host "[WARN] AZURE_AI_AGENT_ENDPOINT not found - skipping agent creation." -ForegroundColor Yellow
        Write-Host "       Set AZURE_AI_AGENT_ENDPOINT in .env and run:" -ForegroundColor DarkGray
        Write-Host "       python scripts/create_agent.py --scenario azure_search_byod --index-name $resolvedTable --agent-name $agentName" -ForegroundColor DarkGray
    }

    # Auto-enrich the data source for rich insights
    Write-Host ""
    Write-Host "Enriching data source for richer insights..." -ForegroundColor Cyan
    Write-Host "(This process extracts topics, summaries, entities, and key phrases)" -ForegroundColor Gray
    Write-Host ""

    & (Join-Path $PSScriptRoot "enrich-byod-data.ps1") -SourceId $resolvedTable -SourceType "azure_search"

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✨ Data source enrichment complete!" -ForegroundColor Green
        Write-Host "   Your Azure AI Search index now has:" -ForegroundColor Gray
        Write-Host "   • Extracted topics and themes" -ForegroundColor Gray
        Write-Host "   • AI-generated summaries" -ForegroundColor Gray
        Write-Host "   • Key phrases and entities" -ForegroundColor Gray
        Write-Host "   • Rich insights and visualizations" -ForegroundColor Gray
    } else {
        Write-Host ""
        Write-Host "⚠️  Enrichment encountered issues (non-critical)." -ForegroundColor Yellow
        Write-Host "   You can manually enrich later with:" -ForegroundColor DarkGray
        Write-Host "   ./scripts/enrich-byod-data.ps1 -SourceId <your-index-name> -SourceType azure_search" -ForegroundColor DarkGray
    }
}
elseif ($resolvedSourceType -eq "fabric") {
    # Read the actual connection details from the temp file written by connect-data.py
    $lastConnPath = Join-Path $projectRoot ".last_byod_connection.json"
    $resolvedSourceId = $null
    $resolvedName = $Name
    $resolvedTable = $Table
    if (Test-Path $lastConnPath) {
        $lastConn = Get-Content $lastConnPath -Raw | ConvertFrom-Json
        $resolvedSourceId = $lastConn.source_id
        $resolvedName = $lastConn.name
        $resolvedTable = $lastConn.table_or_query
        Remove-Item $lastConnPath -ErrorAction SilentlyContinue
    }

    if (-not $resolvedName)  { $resolvedName  = "fabric-byod" }
    if (-not $resolvedTable) { $resolvedTable = "data" }

    # Agent names: alphanumeric + hyphens only, start/end alphanumeric, max 63 chars
    $agentName = ("agent-" + ($resolvedName -replace '[^a-zA-Z0-9]', '-').ToLower().Trim('-'))
    $agentName = $agentName -replace '-{2,}', '-'   # collapse consecutive hyphens
    $agentName = $agentName.Substring(0, [Math]::Min($agentName.Length, 63)).TrimEnd('-')

    # Read AZURE_AI_AGENT_ENDPOINT
    $agentEndpoint = azd env get-value AZURE_AI_AGENT_ENDPOINT 2>$null
    if (-not $agentEndpoint) {
        $envFile = Join-Path $projectRoot ".env"
        if (Test-Path $envFile) {
            $agentEndpoint = (Get-Content $envFile | Where-Object { $_ -match '^AZURE_AI_AGENT_ENDPOINT=' }) -replace '^AZURE_AI_AGENT_ENDPOINT=', ''
        }
    }

    if ($agentEndpoint) {
        Write-Host ""
        Write-Host "Creating AI agents for conversational access..." -ForegroundColor Cyan

        $agentArgs = @(
            (Join-Path $PSScriptRoot "create_agent.py"),
            "--scenario", "fabric_byod",
            "--data-source-type", "fabric",
            "--data-source-name", $resolvedName,
            "--data-source-table", $resolvedTable,
            "--agent-name", $agentName
        )

        & $pythonExe @agentArgs

        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Agents created and ready." -ForegroundColor Green
            Sync-AgentSettingsToApi -ProjectRoot $projectRoot
        } else {
            Write-Host "[WARN] Agent creation encountered errors. You can retry:" -ForegroundColor Yellow
            Write-Host "       python scripts/create_agent.py --scenario fabric_byod --data-source-type fabric --data-source-name $resolvedName --agent-name $agentName" -ForegroundColor DarkGray
        }
    } else {
        Write-Host ""
        Write-Host "[WARN] AZURE_AI_AGENT_ENDPOINT not found - skipping agent creation." -ForegroundColor Yellow
        Write-Host "       Set AZURE_AI_AGENT_ENDPOINT in .env and run:" -ForegroundColor DarkGray
        Write-Host "       python scripts/create_agent.py --scenario fabric_byod --data-source-type fabric --data-source-name $resolvedName --agent-name $agentName" -ForegroundColor DarkGray
    }

    # Auto-enrich the data source for rich insights
    if ($resolvedSourceId) {
        Write-Host ""
        Write-Host "Enriching Fabric data source for richer insights..." -ForegroundColor Cyan
        Write-Host "(This process extracts topics, summaries, entities, and key phrases)" -ForegroundColor Gray
        Write-Host ""

        & (Join-Path $PSScriptRoot "enrich-byod-data.ps1") -SourceId $resolvedSourceId -SourceType "fabric"

        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "✨ Fabric data source enrichment complete!" -ForegroundColor Green
            Write-Host "   Your Fabric table now has:" -ForegroundColor Gray
            Write-Host "   • Extracted topics and themes" -ForegroundColor Gray
            Write-Host "   • AI-generated summaries" -ForegroundColor Gray
            Write-Host "   • Key phrases and entities" -ForegroundColor Gray
            Write-Host "   • Rich insights and visualizations" -ForegroundColor Gray
        } else {
            Write-Host ""
            Write-Host "⚠️  Enrichment encountered issues (non-critical)." -ForegroundColor Yellow
            Write-Host "   You can manually enrich later with:" -ForegroundColor DarkGray
            Write-Host "   ./scripts/enrich-byod-data.ps1 -SourceId <your-connection-id> -SourceType fabric" -ForegroundColor DarkGray
        }
    }
}
