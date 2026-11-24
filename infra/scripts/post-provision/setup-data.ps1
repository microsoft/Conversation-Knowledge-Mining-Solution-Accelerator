#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Post-deployment data setup for Knowledge Mining.
.DESCRIPTION
    Unified script to load data into the app after deployment. Supports:
      - Load a built-in scenario pack (defined in data/config/scenarios.json)
    - Connect an external data source (Azure AI Search, Microsoft Fabric)
      - Upload files from a local folder via -DataPath (used internally by scenarios)

    Scenario packs ship with sample data under data/<scenario_folder>/.
    Raw files are processed through the Content Understanding pipeline.
    Documents can also be uploaded from the web UI after deployment.

.EXAMPLE
    # Interactive — choose scenario or data source
    ./infra/scripts/post-provision/setup-data.ps1

    # Load a scenario pack
    ./infra/scripts/post-provision/setup-data.ps1 -Scenario contact-center
    ./infra/scripts/post-provision/setup-data.ps1 -Scenario mortgage-application
    ./infra/scripts/post-provision/setup-data.ps1 -Scenario telecom-analysis

    # Connect Azure AI Search index
    ./infra/scripts/post-provision/setup-data.ps1 -ExternalSource azure_search -Name "My Index" -Endpoint "https://my-search.search.windows.net" -Table "my-index"
#>

param(
    [ValidateSet("contact-center", "mortgage-application", "telecom-analysis", "insurance-claims")]
    [string]$Scenario,

    [string]$DataPath,
    [switch]$UseSampleData,
    [switch]$ClearExisting,

    # External data source params
    [ValidateSet("azure_search", "fabric")]
    [string]$ExternalSource,
    [string]$Name,
    [string]$Endpoint,
    [string]$Database,
    [string]$Table,
    [string]$ConnectionString,

    [string]$BackendUrl = "http://localhost:8000",
    [switch]$AllowDeployedFallback,

    # Resource group for non-azd / AVM deployments; used to auto-discover the
    # deployed backend and threaded down to child scripts (setup-agent/connect-data).
    [string]$ResourceGroupName
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Knowledge Mining — Data Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path

# Resolve the Python interpreter — prefer the project virtual environment, which
# has the pinned SDK versions (requirements.txt). Fall back to PATH python.
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) { $pythonExe = "python" }
# Cache of the deployed backend's app settings, populated once per resource group.
$script:RgAppSettingsCache = $null
$script:RgApiAppName = ""
$azdAvailable = [bool](Get-Command azd -ErrorAction SilentlyContinue)

# Read every app setting from the api-* App Service in the resource group (cached).
# This is the source of truth when a resource group is targeted explicitly.
function Get-RgAppSettings {
    param([string]$Rg)
    if (-not $Rg) { return @{} }
    if ($null -ne $script:RgAppSettingsCache) { return $script:RgAppSettingsCache }

    $settings = @{}
    $names = (az webapp list --resource-group $Rg --query "[].name" -o tsv)
    if ($LASTEXITCODE -ne 0) { throw "Could not list App Services in '$Rg'. Check Azure CLI sign-in and resource-group access." }
    $apiApps = @(($names -split "`n") | ForEach-Object { $_.Trim() } | Where-Object { $_ -like "api-*" })
    if ($apiApps.Count -ne 1) {
        throw "Expected one api-* App Service in '$Rg'; found $($apiApps.Count). Target the resource group for this deployment."
    }
    $script:RgApiAppName = $apiApps[0]
    $json = (az webapp config appsettings list --name $script:RgApiAppName --resource-group $Rg -o json)
    if ($LASTEXITCODE -ne 0 -or -not $json) {
        throw "Could not read backend app settings in '$Rg'. Check App Service configuration permissions."
    }
    foreach ($kv in ($json | ConvertFrom-Json)) {
        $settings[$kv.name] = $kv.value
    }
    $script:RgAppSettingsCache = $settings
    return $settings
}

function Get-DeployValue {
    param([string]$Name)

    # When a resource group is targeted, config MUST come from the deployed backend
    # in that group — the local azd env may point at an unrelated deployment.
    if ($ResourceGroupName) {
        $rgSettings = Get-RgAppSettings $ResourceGroupName
        if ($rgSettings.Contains($Name)) { return "$($rgSettings[$Name])".Trim() }
        return ""
    }

    if ($azdAvailable) {
        $val = azd env get-value $Name 2>$null
        if ($LASTEXITCODE -eq 0 -and $val -and "$val" -notmatch '^ERROR:') {
            return "$val".Trim()
        }
    }
    $val = [Environment]::GetEnvironmentVariable($Name)
    if (-not [string]::IsNullOrWhiteSpace($val)) { return $val.Trim() }
    $envFile = Join-Path $projectRoot ".env"
    if (Test-Path $envFile) {
        $pattern = "^$([regex]::Escape($Name))="
        $line = Get-Content $envFile | Where-Object { $_ -match $pattern } | Select-Object -First 1
        if ($line) {
            $value = ($line -replace $pattern, '').Trim()
            if ($value -match '^"(.*)"$' -or $value -match "^'(.*)'$") { return $Matches[1] }
            return $value
        }
    }
    return ""
}

# Discover the deployed backend URL from an api-* App Service in the resource group.
# Used for non-azd / AVM deployments where no local backend is running.
function Get-DiscoveredBackendUrl {
    param([string]$Rg)
    if (-not $Rg) { return "" }
    Get-RgAppSettings $Rg | Out-Null
    $hostName = (az webapp show --name $script:RgApiAppName --resource-group $Rg --query defaultHostName -o tsv)
    if ($LASTEXITCODE -ne 0 -or -not $hostName) { throw "Could not resolve the backend hostname in '$Rg'." }
    return "https://$($hostName.Trim())"
}

# ── Load scenarios config (used by interactive menu and scenario resolution) ──
$configPath = Join-Path $projectRoot "data" "config" "scenarios.json"
$scenarioConfig = Get-Content $configPath -Raw | ConvertFrom-Json

function Resolve-ScenarioDataPath {
    param(
        [string]$Root,
        [string]$ScenarioKey,
        [string]$ConfiguredFolder
    )

    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($ConfiguredFolder) { $candidates.Add($ConfiguredFolder) }

    switch ($ScenarioKey) {
        "mortgage-application" {
            $candidates.Add("MortgageApplication_usecase")
            $candidates.Add("MorgageApplication_usecase")
        }
        "telecom-analysis" {
            $candidates.Add("telecom_analysis_usecase")
            $candidates.Add("telecom_analysis_uscase")
        }
        "contact-center" {
            $candidates.Add("ContactCenter_usecase")
            $candidates.Add("ContactCeneter_usecase")
        }
    }

    foreach ($folder in ($candidates | Select-Object -Unique)) {
        if (-not $folder) { continue }
        $path = Join-Path $Root "data" $folder
        if (Test-Path $path) {
            return $path
        }
    }

    return $null
}

function Test-BackendReachable {
    param([string]$Url)
    try {
        # Probe the anonymous root, not an authenticated ingestion endpoint.
        Invoke-RestMethod -Uri "$($Url.TrimEnd('/'))/" -Method GET -TimeoutSec 3 -SkipHttpErrorCheck | Out-Null
        return $true
    } catch {
        Write-Host "Backend at $Url is not responding; checking the next configured address." -ForegroundColor DarkGray
        return $false
    }
}

# ── Resolve backend URL ──
if ($PSBoundParameters.ContainsKey("BackendUrl")) {
    Write-Host "Using explicit backend: $BackendUrl" -ForegroundColor Yellow
}
elseif ($ResourceGroupName) {
    # Non-azd / AVM deployment: target the deployed backend discovered from the resource group.
    $discovered = Get-DiscoveredBackendUrl $ResourceGroupName
    if ($discovered) {
        $BackendUrl = $discovered
        Write-Host "Using deployed backend discovered from resource group '$ResourceGroupName': $BackendUrl" -ForegroundColor Yellow
    } else {
        Write-Host "ERROR: Could not discover the backend App Service (api-*) in resource group '$ResourceGroupName'." -ForegroundColor Red
        exit 1
    }
}
elseif ($BackendUrl -eq "http://localhost:8000") {
    $localHealthy = Test-BackendReachable $BackendUrl

    if (-not $localHealthy) {
        $loopbackUrl = "http://127.0.0.1:8000"
        if (Test-BackendReachable $loopbackUrl) {
            $BackendUrl = $loopbackUrl
            $localHealthy = $true
        }
    }

    if ($localHealthy) {
        Write-Host "Using local backend: $BackendUrl" -ForegroundColor Yellow
    } else {
        if ($AllowDeployedFallback -or $env:KM_ALLOW_DEPLOYED_BACKEND_FALLBACK -eq "1") {
            $azdUrl = Get-DeployValue "SERVICE_BACKEND_URI"
            if ($azdUrl) {
                Write-Host "Using deployed backend: $azdUrl" -ForegroundColor Yellow
                $BackendUrl = $azdUrl
            } else {
                Write-Host "ERROR: Local backend is unavailable and no deployed backend is configured." -ForegroundColor Red
                exit 1
            }
        } else {
            Write-Host "ERROR: Local backend is unavailable at $BackendUrl." -ForegroundColor Red
            Write-Host "Start the local API first, pass -BackendUrl explicitly, or use -AllowDeployedFallback to target the deployed backend intentionally." -ForegroundColor Yellow
            exit 1
        }
    }
}

function Get-ApiHeaders {
    $adminKey = Get-DeployValue "ADMIN_API_KEY"
    if ($adminKey) {
        Write-Host "Using configured admin API key for script authentication" -ForegroundColor Yellow
        return @{ "X-Admin-Api-Key" = $adminKey }
    }
    $clientId = Get-DeployValue "AZURE_AD_CLIENT_ID"
    $tenantId = Get-DeployValue "AZURE_AD_TENANT_ID"
    if (-not $clientId -or -not $tenantId) {
        throw "Configure AZURE_AD_CLIENT_ID and AZURE_AD_TENANT_ID, or ADMIN_API_KEY, for the targeted backend. See docs/AppAuthentication.md."
    }
    $token = az account get-access-token --tenant $tenantId --resource "api://$clientId" --query accessToken -o tsv 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $token -or "$token" -match '^ERROR:') {
        throw "Could not obtain an API access token. Run az login for the API tenant, grant Azure CLI consent to the API scope, and assign the required app role; alternatively configure ADMIN_API_KEY. See docs/AppAuthentication.md."
    }
    return @{ Authorization = "Bearer $($token.Trim())" }
}

function Assert-ApiRole {
    param([ValidateSet("contributor", "admin")][string]$RequiredRole = "contributor")
    if ($script:ApiRole -eq "admin" -or ($RequiredRole -eq "contributor" -and $script:ApiRole -eq "contributor")) { return }
    throw "Data setup requires the '$RequiredRole' app role for this operation. Assign it in Entra ID or use the targeted backend's ADMIN_API_KEY."
}

function Test-ApiAccess {
    param([string]$Url, [hashtable]$Headers)
    $authStatus = 0
    try {
        $user = Invoke-RestMethod -Uri "$Url/api/auth/me" -Method GET -Headers $Headers -TimeoutSec 30 `
            -SkipHttpErrorCheck -StatusCodeVariable authStatus
    } catch {
        throw "Could not reach the backend authentication endpoint. Check App Service access restrictions, private networking, and the backend URL."
    }
    switch ($authStatus) {
        200 {
            $script:ApiRole = if ($user.roles -contains "Admin") { "admin" } elseif ($user.roles -contains "Contributor") { "contributor" } else { "reader" }
            Assert-ApiRole
        }
        401 { throw "Backend rejected the API credentials (HTTP 401). Check the target app's ADMIN_API_KEY or Entra tenant, audience, API scope, and token lifetime." }
        403 { throw "Backend access denied (HTTP 403). Check App Service/EasyAuth access restrictions and private-network connectivity; an API key cannot bypass platform restrictions." }
        503 { throw "Backend authentication is unavailable (HTTP 503). Configure both Entra IDs on the deployed API and verify its signing-key connectivity." }
        default { throw "Backend authentication preflight failed (HTTP $authStatus). Check the backend URL and deployment health." }
    }
}

$backendUri = $null
if (-not [Uri]::TryCreate($BackendUrl, [UriKind]::Absolute, [ref]$backendUri) -or
    $backendUri.Scheme -notin @("http", "https") -or $backendUri.UserInfo -or $backendUri.Query -or $backendUri.Fragment) {
    throw "BackendUrl must be an absolute HTTP(S) URL without credentials, a query, or a fragment."
}
if ($backendUri.Scheme -eq "http" -and -not $backendUri.IsLoopback) {
    throw "Use HTTPS for remote backends to protect API credentials."
}
$BackendUrl = $BackendUrl.TrimEnd("/")
$headers = Get-ApiHeaders
Test-ApiAccess -Url $BackendUrl -Headers $headers
if ($Scenario -or $UseSampleData -or $ExternalSource -or $ClearExisting -or -not $DataPath) {
    Assert-ApiRole -RequiredRole "admin"
}

# Child Python scripts read configuration from process environment before .env.
if ($ResourceGroupName) {
    foreach ($entry in (Get-RgAppSettings $ResourceGroupName).GetEnumerator()) {
        Set-Item -Path "Env:$($entry.Key)" -Value $entry.Value
    }
    $env:RESOURCE_GROUP_NAME = $ResourceGroupName
    $env:AZURE_RESOURCE_GROUP = $ResourceGroupName
    $env:API_APP_NAME = $script:RgApiAppName
}
$env:BACKEND_URL = $BackendUrl
$env:KM_SKIP_LOCAL_ENV = if ($ResourceGroupName) { "1" } else { "0" }
# Clear stale keys as well as forwarding the selected deployment's script key.
$env:ADMIN_API_KEY = Get-DeployValue "ADMIN_API_KEY"
$env:KM_API_ACCESS_TOKEN = if ($headers.ContainsKey("Authorization")) {
    $headers["Authorization"] -replace '^Bearer ', ''
} else { "" }

# ── Wait for the backend's SQL connection to actually be ready ──
# Right after a fresh deploy/restart, the container can come up and answer HTTP
# requests before its managed identity's SQL role has finished propagating. Any
# SQL-backed write attempted in that window (e.g. scenario registration below)
# silently fails while still returning 200 OK to the caller. Poll the deep health
# endpoint here — before any registration/cleanup call — so we only proceed once
# the backend reports SQL as actually reachable, closing the race at its source.
function Wait-ForBackendSqlHealthy {
    param(
        [string]$BackendUrl,
        [hashtable]$Headers,
        [ValidateSet("sql", "cosmos")][string]$DatabaseProvider = "sql",
        [ValidateRange(1, 2147483647)][int]$TimeoutSec = 300,
        [ValidateRange(1, 2147483647)][int]$PollIntervalSec = 10
    )

    Write-Host "Waiting for backend $DatabaseProvider connectivity to be ready..." -ForegroundColor Yellow
    $healthUrl = "$($BackendUrl.TrimEnd('/'))/api/health"
    $elapsed = 0
    while ($elapsed -lt $TimeoutSec) {
        $healthStatus = 0
        $resp = $null
        try {
            $resp = Invoke-RestMethod -Uri $healthUrl -Method GET -Headers $Headers -TimeoutSec 10 `
                -SkipHttpErrorCheck -StatusCodeVariable healthStatus
        } catch {
            Write-Host "  Backend not reachable yet — retrying in ${PollIntervalSec}s..." -ForegroundColor DarkGray
        }
        if ($healthStatus -in @(401, 403)) {
            throw "Backend health access denied (HTTP $healthStatus). Check credentials, App Service restrictions, and private-network access before retrying."
        }
        if ($healthStatus -eq 404) { throw "Backend health endpoint was not found. Check BackendUrl." }
        if ($healthStatus -in @(200, 503) -and $resp.checks.$DatabaseProvider -eq "ok") {
            Write-Host "Backend $DatabaseProvider is ready." -ForegroundColor Green
            return $true
        }
        Write-Host "  $DatabaseProvider not ready (HTTP $healthStatus, checks.$DatabaseProvider=$($resp.checks.$DatabaseProvider)) — retrying..." -ForegroundColor DarkGray
        Start-Sleep -Seconds $PollIntervalSec
        $elapsed += $PollIntervalSec
    }
    throw "Timed out waiting for backend $DatabaseProvider access. Setup stopped before changing data. For SQL, verify the API managed identity's contained user/roles (setup-sql-roles.ps1), SQL firewall/private endpoints, and backend logs."
}

$databaseProvider = Get-DeployValue "DATABASE_PROVIDER"
if (-not $databaseProvider) { $databaseProvider = "sql" }
Wait-ForBackendSqlHealthy -BackendUrl $BackendUrl -Headers $headers -DatabaseProvider $databaseProvider.ToLowerInvariant() | Out-Null

# ── Shared cleanup: clear demo data + external source connections for scenario isolation ──
function Invoke-DataCleanup {
    param(
        [string]$BackendUrl,
        [hashtable]$Headers
    )

    Assert-ApiRole -RequiredRole "admin"
    # Clear existing demo data (documents, insights cache) and any external data source
    # registrations so every scenario starts from a clean slate.
    Write-Host "Clearing existing data and external source connections for scenario isolation..." -ForegroundColor Yellow
    try {
        Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/clear?include_external=true" -Method DELETE -Headers $Headers | Out-Null
        Write-Host "Previous data and external source registrations cleared." -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Could not clear existing data before scenario load: $_" -ForegroundColor Red
        Write-Host "Aborting to prevent mixed data across use cases." -ForegroundColor Yellow
        throw
    }
}

# Confirm the backend accepted and registered the uploaded files, WITHOUT waiting for
# extraction/chunking/embedding/indexing to finish. Full ingestion (Content Understanding
# -> chunk -> embed -> Azure AI Search) runs asynchronously inside the API App Service's own
# background queue worker (src/api/main.py starts it at process startup and it runs for the
# life of the app) using that App Service's private-endpoint/VNet-integrated connectivity to
# Storage/Search/OpenAI/Cosmos/SQL - connectivity that does NOT depend on the temporary
# public network access this script's caller opened. So there is nothing to wait for here:
# once /refresh confirms the files are registered, it is safe to lock the network back down
# (manage-network-access.ps1 -Action Disable) immediately; processing keeps running in the
# background on the deployed App Service regardless. This keeps the temporary public-access
# window (and overall deployment time) as short as possible - check the Sources page in the
# web UI a few minutes later to confirm files have finished processing.
function Confirm-UploadRegistered {
    [CmdletBinding()]
    param(
        [string]$BackendUrl,
        [hashtable]$Headers,
        $ExpectedFiles = @(),
        [int]$TimeoutSec = 90,
        [int]$PollIntervalSec = 10
    )

    $expectedCount = @($ExpectedFiles | Where-Object { $_ }).Count
    if ($expectedCount -eq 0) {
        return [pscustomobject]@{ Registered = 0; Expected = 0 }
    }

    Write-Host ""
    Write-Host "Confirming upload registration (not waiting for background processing)..." -ForegroundColor Yellow

    $elapsed = 0
    $cnt = 0
    while ($elapsed -lt $TimeoutSec) {
        $cnt = -1
        try {
            $r = Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/refresh" -Method POST -Headers $Headers
            $cnt = [int]$r.files
        } catch {
            if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -in @(401, 403)) {
                throw "Upload registration access denied. Check API credentials, app roles, and App Service access restrictions."
            }
            Write-Warning "Could not confirm upload registration; retrying."
        }
        if ($cnt -ge $expectedCount) { break }
        Start-Sleep -Seconds $PollIntervalSec
        $elapsed += $PollIntervalSec
    }

    if ($cnt -ge $expectedCount) {
        Write-Host "  $expectedCount file(s) registered - processing continues in the background." -ForegroundColor Green
    } else {
        throw "Only $([Math]::Max(0, $cnt))/$expectedCount file(s) registered after ${elapsed}s. Setup did not complete; check backend storage access and the Sources page."
    }
    return [pscustomobject]@{ Registered = [Math]::Max(0, $cnt); Expected = $expectedCount }
}


# Ensure the solution search index exists
function Invoke-EnsureSearchIndex {
    Write-Host "Ensuring search index exists..." -ForegroundColor Yellow
    $searchEndpoint = Get-DeployValue "AZURE_SEARCH_ENDPOINT"
    $searchIndexName = Get-DeployValue "AZURE_SEARCH_INDEX_NAME"
    $openaiEndpoint = Get-DeployValue "AZURE_OPENAI_ENDPOINT"
    $embeddingDeployment = Get-DeployValue "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
    $idxArgs = @((Join-Path $PSScriptRoot "create_search_index.py"))
    if ($searchEndpoint)      { $idxArgs += "--search-endpoint", $searchEndpoint }
    if ($searchIndexName)     { $idxArgs += "--index-name", $searchIndexName }
    if ($openaiEndpoint)      { $idxArgs += "--openai-endpoint", $openaiEndpoint }
    if ($embeddingDeployment) { $idxArgs += "--embedding-deployment", $embeddingDeployment }
    & $pythonExe @idxArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Could not ensure the search index. Check the deployer's Azure AI Search permissions and network access."
    }
}

# ── Interactive mode if no params ──
if (-not $Scenario -and -not $DataPath -and -not $UseSampleData -and -not $ExternalSource) {
    # Build menu dynamically from scenarios.json
    $menuItems = [System.Collections.ArrayList]::new()

    # Add scenarios
    foreach ($key in $scenarioConfig.scenarios.PSObject.Properties.Name) {
        $s = $scenarioConfig.scenarios.$key
        if ($s.skip) { continue }
        $null = $menuItems.Add(@{ type = "scenario"; key = $key; name = $s.name; description = $s.description })
    }

    # Add data sources
    if ($scenarioConfig.data_sources) {
        foreach ($key in $scenarioConfig.data_sources.PSObject.Properties.Name) {
            $ds = $scenarioConfig.data_sources.$key
            $null = $menuItems.Add(@{ type = "data_source"; key = $key; name = $ds.name; description = $ds.description })
        }
    }

    # Add fixed options
    $null = $menuItems.Add(@{ type = "skip"; key = "skip"; name = "Skip"; description = "Set up data later (you can upload documents from the web UI)" })

    Write-Host "Choose how to load data:" -ForegroundColor White
    Write-Host ""

    for ($i = 0; $i -lt $menuItems.Count; $i++) {
        $item = $menuItems[$i]
        $num = $i + 1
        $label = if ($item.type -eq "data_source") { "$($item.name) (connect)" } else { $item.name }
        Write-Host "  $num. $label" -ForegroundColor White
        Write-Host "     $($item.description)" -ForegroundColor DarkGray
    }
    Write-Host ""

    $maxChoice = $menuItems.Count
    do {
        $choice = Read-Host "Enter choice (1-$maxChoice)"
        $valid = $choice -match '^\d+$' -and [int]$choice -ge 1 -and [int]$choice -le $maxChoice
        if (-not $valid) { Write-Host "Please enter a number between 1 and $maxChoice." -ForegroundColor Yellow }
    } while (-not $valid)

    $selected = $menuItems[[int]$choice - 1]

    switch ($selected.type) {
        "scenario" {
            # BYOD scenarios: connect data source then create agents
            if ($selected.key -in @("azure_search_byod", "fabric_byod")) {
                $sourceType = if ($selected.key -eq "azure_search_byod") { "azure_search" } else { "fabric" }
                Write-Host ""
                # Clear existing data + external sources first (same as scenarios 1-3) for isolation.
                Invoke-DataCleanup -BackendUrl $BackendUrl -Headers $headers
                Write-Host ""
                $env:BACKEND_URL = $BackendUrl
                & (Join-Path $PSScriptRoot "connect-data.ps1") -Type $sourceType -ResourceGroupName $ResourceGroupName
                exit $LASTEXITCODE
            }
            $Scenario = $selected.key
        }
        "data_source" {
            Write-Host ""
            # Clear existing data + external sources first (same as scenarios 1-3) for isolation.
            Invoke-DataCleanup -BackendUrl $BackendUrl -Headers $headers
            Write-Host ""
            $env:BACKEND_URL = $BackendUrl
            & (Join-Path $PSScriptRoot "connect-data.ps1") -Type $selected.key -ResourceGroupName $ResourceGroupName
            exit $LASTEXITCODE
        }
        "skip" {
            Write-Host ""
            Write-Host "Skipped data loading. You can upload documents from the web UI." -ForegroundColor Yellow
            Write-Host ""
            Invoke-EnsureSearchIndex
            Write-Host ""
            Write-Host "Creating default AI agent with SQL and Azure AI Search tools..." -ForegroundColor Yellow
            & (Join-Path $PSScriptRoot "setup-agent.ps1") -Scenario "skip" -ResourceGroupName $ResourceGroupName
            if ($LASTEXITCODE -ne 0) {
                Write-Host "WARNING: Agent setup failed — retry with: ./infra/scripts/post-provision/setup-agent.ps1 -Scenario skip" -ForegroundColor Yellow
            }
            exit $LASTEXITCODE
        }
    }
}

# ── Resolve scenario to data path ──
if ($Scenario) {
    $pack = $scenarioConfig.scenarios.$Scenario

    if (-not $pack) {
        $available = ($scenarioConfig.scenarios.PSObject.Properties.Name) -join ", "
        Write-Host "ERROR: Unknown scenario '$Scenario'." -ForegroundColor Red
        Write-Host "Available: $available" -ForegroundColor Yellow
        exit 1
    }

    Write-Host ""
    Write-Host "Scenario: $($pack.name)" -ForegroundColor Cyan
    Write-Host "  $($pack.description)" -ForegroundColor White
    Write-Host ""

    $scenarioDataPath = Resolve-ScenarioDataPath -Root $projectRoot -ScenarioKey $Scenario -ConfiguredFolder $pack.data_folder

    if (-not $scenarioDataPath) {
        Write-Host "ERROR: Scenario data folder not found for '$Scenario'." -ForegroundColor Red
        Write-Host "Checked configured and known variant folder names under data/." -ForegroundColor Yellow
        exit 1
    }

    # Update UI config with scenario name
    $uiConfigPath = Join-Path $projectRoot "src" "app" "src" "config" "ui-config.json"
    if (Test-Path $uiConfigPath) {
        $uiConfig = Get-Content $uiConfigPath -Raw | ConvertFrom-Json
        $uiConfig.useCaseName = $pack.name
        $uiConfig | ConvertTo-Json -Depth 10 | Set-Content $uiConfigPath -Encoding UTF8
        Write-Host "Updated UI config: useCaseName = '$($pack.name)'" -ForegroundColor Green
    }

    # Always clear existing demo data + external sources before loading any scenario/use case
    Invoke-DataCleanup -BackendUrl $BackendUrl -Headers $headers

    # Register the scenario as an inert 'native' data source so its use-case name
    # surfaces in the UI at runtime without a frontend rebuild.
    try {
        $scenarioBody = @{ name = $pack.name; use_case = $pack.name } | ConvertTo-Json -Compress
        Invoke-RestMethod -Uri "$BackendUrl/api/data-sources/scenario" -Method POST `
            -Headers $headers -ContentType "application/json" -Body $scenarioBody | Out-Null
        Write-Host "Registered scenario use case: '$($pack.name)'" -ForegroundColor Green
    } catch {
        throw "Could not register scenario use case name. Check API authorization and backend SQL access: $($_.Exception.Message)"
    }

    # Create the solution search index (seeded scenarios only)
    Invoke-EnsureSearchIndex

    # Contact Center has pre-processed data — use the direct seed path
    if ($pack.has_preprocessed -eq $true) {
        Write-Host "This scenario has pre-processed data. Loading via seed script..." -ForegroundColor Yellow
        Write-Host ""

        # Export deploy-resolved config so the seed subprocess targets THIS deployment.
        # Overwrites any stale session/.env values (e.g. leftovers from a prior run
        # against a different environment) that seed-sample-data.py would otherwise use.
        foreach ($name in @(
            "AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_INDEX_NAME",
            "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
            "AZURE_COSMOS_ENDPOINT", "AZURE_COSMOS_DATABASE",
            "AZURE_SQL_SERVER", "AZURE_SQL_DATABASE"
        )) {
            $val = Get-DeployValue $name
            Set-Item -Path "Env:$name" -Value $val
        }

        # Run seed-sample-data.py with the scenario data directory
        $env:KM_SCENARIO_DATA_DIR = $scenarioDataPath
        $env:BACKEND_URL = $BackendUrl
        & $pythonExe (Join-Path $PSScriptRoot "seed-sample-data.py")

        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "Scenario '$($pack.name)' loaded successfully!" -ForegroundColor Green
        } else {
            Write-Host "Scenario loading encountered errors." -ForegroundColor Red
            exit 1
        }
    } else {
        # Non-preprocessed scenarios — upload raw files through the API
        $DataPath = $scenarioDataPath
    }
}

# ── Clear existing data ──
if ($ClearExisting -or (-not $UseSampleData -and -not $ExternalSource -and -not $Scenario)) {
    Write-Host ""
    if (-not $ClearExisting) {
        $confirm = Read-Host "Clear existing data before loading? (y/N)"
        if ($confirm -eq "y" -or $confirm -eq "Y") { $ClearExisting = $true }
    }
    if ($ClearExisting) {
        Invoke-DataCleanup -BackendUrl $BackendUrl -Headers $headers
    }
}

# ══════════════════════════════════════════
# Option 1: Upload files from a folder
# ══════════════════════════════════════════
if ($DataPath) {
    if (-not (Test-Path $DataPath)) {
        Write-Host "ERROR: Path not found: $DataPath" -ForegroundColor Red
        exit 1
    }

    $allFiles = Get-ChildItem $DataPath -File
    $audioFiles = $allFiles | Where-Object { $_.Extension -in ".wav", ".mp3", ".mp4" }
    $docFiles = $allFiles | Where-Object { $_.Extension -in ".pdf", ".docx", ".xlsx", ".csv", ".txt", ".json", ".png", ".jpg", ".jpeg" }

    Write-Host ""
    Write-Host "Found in $DataPath :" -ForegroundColor White
    if ($audioFiles.Count -gt 0) { Write-Host "  $($audioFiles.Count) audio files (WAV/MP3)" -ForegroundColor Cyan }
    if ($docFiles.Count -gt 0) { Write-Host "  $($docFiles.Count) document files (PDF/JSON/DOCX/etc.)" -ForegroundColor Cyan }
    Write-Host ""

    $audioUploaded = 0
    $docUploaded = 0
    $uploadFailures = 0

    # ── Audio files (batch upload) ──
    if ($audioFiles.Count -gt 0) {
        Write-Host ""
        Write-Host "Uploading $($audioFiles.Count) audio files (transcription via Content Understanding)..." -ForegroundColor Yellow

        $batchSize = 1
        $success = 0; $failed = 0
        for ($i = 0; $i -lt $audioFiles.Count; $i += $batchSize) {
            $batch = $audioFiles[$i..([Math]::Min($i + $batchSize - 1, $audioFiles.Count - 1))]
            $form = @{}
            $fileItems = @()
            foreach ($f in $batch) {
                $fileItems += Get-Item $f.FullName
                Write-Host "  $($f.Name)" -ForegroundColor White
            }
            try {
                Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/upload/document" `
                    -Method POST -Form @{ files = $fileItems } -Headers $headers -TimeoutSec 180 | Out-Null
                $success += $batch.Count
                Write-Host "  Batch of $($batch.Count) submitted" -ForegroundColor Green
            } catch {
                Write-Host "  Batch FAILED: $_" -ForegroundColor Red
                $failed += $batch.Count
            }
        }
        Write-Host "  Audio: $success uploaded, $failed failed" -ForegroundColor $(if ($failed) { "Yellow" } else { "Green" })
        $audioUploaded = $success
        $uploadFailures += $failed
        if ($success -gt 0) {
            Write-Host "  Audio files are processing in background — check Sources page for status." -ForegroundColor Cyan
        }
    }

    # ── Document files (batch upload) ──
    if ($docFiles.Count -gt 0) {
        Write-Host ""
        Write-Host "Uploading $($docFiles.Count) document files..." -ForegroundColor Yellow

        # Upload in batches of 5
        $batchSize = 5
        $success = 0; $failed = 0
        for ($i = 0; $i -lt $docFiles.Count; $i += $batchSize) {
            $batch = $docFiles[$i..([Math]::Min($i + $batchSize - 1, $docFiles.Count - 1))]
            $fileItems = @()
            foreach ($f in $batch) {
                $fileItems += Get-Item $f.FullName
                Write-Host "  $($f.Name)" -ForegroundColor White
            }
            try {
                Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/upload/document" `
                    -Method POST -Form @{ files = $fileItems } -Headers $headers -TimeoutSec 180 | Out-Null
                $success += $batch.Count
                Write-Host "  Batch of $($batch.Count) submitted" -ForegroundColor Green
            } catch {
                Write-Host "  Batch FAILED: $_" -ForegroundColor Red
                $failed += $batch.Count
            }
        }
        Write-Host "  Documents: $success uploaded, $failed failed" -ForegroundColor $(if ($failed) { "Yellow" } else { "Green" })
        $docUploaded = $success
        $uploadFailures += $failed
    }

    if ($uploadFailures -gt 0) {
        throw "$uploadFailures file(s) failed to upload. Setup did not complete; check API credentials, ingestion permissions, and backend storage access."
    }

    $registration = $null
    if ($audioFiles.Count -gt 0 -or $docFiles.Count -gt 0) {
        # Confirm registration only — do NOT wait for extraction/chunking/embedding/indexing.
        # See Confirm-UploadRegistered for why: that work continues in the background on the
        # deployed App Service regardless of what this deployer-side script does next.
        $expectedItems = @()
        if ($audioFiles) { $expectedItems += $audioFiles }
        if ($docFiles)   { $expectedItems += $docFiles }
        $registration = Confirm-UploadRegistered -BackendUrl $BackendUrl -Headers $headers -ExpectedFiles $expectedItems
    }

    Write-Host ""
    if ($registration -and $registration.Registered -lt $registration.Expected) {
        Write-Host "Data upload finished — $($registration.Registered)/$($registration.Expected) file(s) registered. Processing continues in the background; check the Sources page." -ForegroundColor Yellow
    } else {
        Write-Host "Data upload complete! Files are processing in the background — check the Sources page for status." -ForegroundColor Green
    }
}

# ══════════════════════════════════════════
# Option 2: Connect external data source
# ══════════════════════════════════════════
if ($ExternalSource) {
    # Clear existing data + external sources first (same as scenarios 1-3) for isolation.
    Invoke-DataCleanup -BackendUrl $BackendUrl -Headers $headers
    Write-Host ""

    $env:BACKEND_URL = $BackendUrl
    $pyArgs = @("--type", $ExternalSource)
    if ($Name)             { $pyArgs += "--name", $Name }
    if ($Endpoint)         { $pyArgs += "--endpoint", $Endpoint }
    if ($Database)         { $pyArgs += "--database", $Database }
    if ($Table)            { $pyArgs += "--table", $Table }
    if ($ConnectionString) { $pyArgs += "--connection-string", $ConnectionString }

    & $pythonExe (Join-Path $PSScriptRoot "connect-data.py") @pyArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "External data source connection failed." -ForegroundColor Red
        exit 1
    }
}

# ══════════════════════════════════════════
# Option 3: Load built-in sample data
# ══════════════════════════════════════════
if ($UseSampleData) {
    Assert-ApiRole -RequiredRole "admin"
    Write-Host "Loading built-in sample dataset..." -ForegroundColor Yellow
    try {
        $result = Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/load-default" `
            -Method POST -Headers $headers -ContentType "application/json"
        Write-Host "Loaded $($result.total_loaded) documents" -ForegroundColor Green
    } catch {
        Write-Host "Failed to load sample data: $_" -ForegroundColor Red
        exit 1
    }
}

# ══════════════════════════════════════════
# Create scenario-based AI agent
# ══════════════════════════════════════════
# The agent prompt is dynamic per scenario (SQL+Search vs Search-only), so the
# agent is (re)created here once the scenario data is loaded.
if ($Scenario) {
    Write-Host ""
    Write-Host "Creating scenario-based AI agent for '$Scenario'..." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "setup-agent.ps1") -Scenario $Scenario -ResourceGroupName $ResourceGroupName
    if ($LASTEXITCODE -ne 0) {
        throw "Agent setup failed. Check Foundry project permissions and retry setup-agent.ps1 for scenario '$Scenario'."
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
exit 0
