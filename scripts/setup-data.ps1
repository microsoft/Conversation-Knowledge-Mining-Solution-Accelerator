#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Post-deployment data setup for Knowledge Mining.
.DESCRIPTION
    Unified script to load data into the app after deployment. Supports:
      - Load a built-in scenario pack (defined in data/config/scenarios.json)
      - Connect an external data source (Azure AI Search, Fabric, SQL, Synapse)
      - Upload files from a local folder via -DataPath (used internally by scenarios)

    Scenario packs ship with sample data under data/<scenario_folder>/.
    Raw files are processed through the Content Understanding pipeline.
    Documents can also be uploaded from the web UI after deployment.

.EXAMPLE
    # Interactive — choose scenario or data source
    ./scripts/setup-data.ps1

    # Load a scenario pack
    ./scripts/setup-data.ps1 -Scenario contact-center
    ./scripts/setup-data.ps1 -Scenario mortgage-application
    ./scripts/setup-data.ps1 -Scenario telecom-analysis

    # Connect Azure AI Search index
    ./scripts/setup-data.ps1 -ExternalSource azure_search -Name "My Index" -Endpoint "https://my-search.search.windows.net" -Table "my-index"
#>

param(
    [ValidateSet("contact-center", "mortgage-application", "telecom-analysis")]
    [string]$Scenario,

    [string]$DataPath,
    [switch]$UseSampleData,
    [switch]$ClearExisting,

    # External data source params
    [ValidateSet("azure_search", "fabric", "sql", "synapse")]
    [string]$ExternalSource,
    [string]$Name,
    [string]$Endpoint,
    [string]$Database,
    [string]$Table,
    [string]$ConnectionString,

    [string]$BackendUrl = "http://localhost:8000",
    [switch]$AllowDeployedFallback
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Knowledge Mining — Data Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$projectRoot = Split-Path -Parent $PSScriptRoot

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

# ── Resolve backend URL ──
if ($PSBoundParameters.ContainsKey("BackendUrl")) {
    Write-Host "Using explicit backend: $BackendUrl" -ForegroundColor Yellow
}
elseif ($BackendUrl -eq "http://localhost:8000") {
    $localHealthy = $false
    try {
        Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/stats" -Method GET -TimeoutSec 3 | Out-Null
        $localHealthy = $true
    } catch {
        $localHealthy = $false
    }

    if (-not $localHealthy) {
        $loopbackUrl = "http://127.0.0.1:8000"
        try {
            Invoke-RestMethod -Uri "$loopbackUrl/api/ingestion/stats" -Method GET -TimeoutSec 3 | Out-Null
            $BackendUrl = $loopbackUrl
            $localHealthy = $true
        } catch {
            $localHealthy = $false
        }
    }

    if ($localHealthy) {
        Write-Host "Using local backend: $BackendUrl" -ForegroundColor Yellow
    } else {
        if ($AllowDeployedFallback -or $env:KM_ALLOW_DEPLOYED_BACKEND_FALLBACK -eq "1") {
            $azdUrl = azd env get-value SERVICE_BACKEND_URI 2>$null
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

# ── Auth token ──
$token = az account get-access-token --resource "api://$(azd env get-value AZURE_AD_CLIENT_ID 2>$null)" --query accessToken -o tsv 2>$null
$headers = @{}
if ($token) {
    $headers["Authorization"] = "Bearer $token"
} else {
    $adminKey = $env:ADMIN_API_KEY
    if (-not $adminKey) {
        $adminKey = azd env get-value ADMIN_API_KEY 2>$null
    }
    if ($adminKey) {
        Write-Host "Using admin API key for local auth" -ForegroundColor Yellow
        $headers["X-Admin-Api-Key"] = $adminKey
    } else {
        Write-Host "No auth token or admin key found — requests may be rejected in prod" -ForegroundColor Yellow
    }
}

# ── Interactive mode if no params ──
if (-not $Scenario -and -not $DataPath -and -not $UseSampleData -and -not $ExternalSource) {
    # Build menu dynamically from scenarios.json
    $menuItems = [System.Collections.ArrayList]::new()

    # Add scenarios
    foreach ($key in $scenarioConfig.scenarios.PSObject.Properties.Name) {
        $s = $scenarioConfig.scenarios.$key
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
        "scenario" { $Scenario = $selected.key }
        "data_source" {
            Write-Host ""
            & (Join-Path $PSScriptRoot "connect-data.ps1") -Type $selected.key
            exit $LASTEXITCODE
        }
        "skip" {
            Write-Host "Skipped. You can upload documents from the web UI." -ForegroundColor Yellow
            exit 0
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

    # Auto-clear existing data before loading a new scenario
    Write-Host "Clearing existing data before loading new scenario..." -ForegroundColor Yellow
    try {
        Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/clear" -Method DELETE -Headers $headers | Out-Null
        Write-Host "Previous data cleared." -ForegroundColor Green
    } catch {
        Write-Host "Warning: Could not clear via API (server may not be running) — $_" -ForegroundColor Yellow
    }

    # Contact Center has pre-processed data — use the direct seed path
    if ($pack.has_preprocessed -eq $true) {
        Write-Host "This scenario has pre-processed data. Loading via seed script..." -ForegroundColor Yellow
        Write-Host ""

        # Run seed-sample-data.py with the scenario data directory
        $env:KM_SCENARIO_DATA_DIR = $scenarioDataPath
        $env:BACKEND_URL = $BackendUrl
        python (Join-Path $PSScriptRoot "seed-sample-data.py")

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
        Write-Host "Clearing existing data..." -ForegroundColor Yellow
        try {
            Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/clear" -Method DELETE -Headers $headers | Out-Null
            Write-Host "Data cleared." -ForegroundColor Green
        } catch {
            Write-Host "Warning: Could not clear data — $_" -ForegroundColor Yellow
        }
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
    $jsonFiles = $allFiles | Where-Object { $_.Extension -eq ".json" }
    $audioFiles = $allFiles | Where-Object { $_.Extension -in ".wav", ".mp3", ".mp4" }
    $docFiles = $allFiles | Where-Object { $_.Extension -in ".pdf", ".docx", ".xlsx", ".txt", ".png", ".jpg", ".jpeg", ".tiff", ".bmp" }

    Write-Host ""
    Write-Host "Found in $DataPath :" -ForegroundColor White
    if ($jsonFiles.Count -gt 0) { Write-Host "  $($jsonFiles.Count) JSON files" -ForegroundColor Cyan }
    if ($audioFiles.Count -gt 0) { Write-Host "  $($audioFiles.Count) audio files (WAV/MP3)" -ForegroundColor Cyan }
    if ($docFiles.Count -gt 0) { Write-Host "  $($docFiles.Count) document files (PDF/DOCX/etc.)" -ForegroundColor Cyan }
    Write-Host ""

    # ── JSON conversations ──
    if ($jsonFiles.Count -gt 0) {
        Write-Host "Processing JSON files..." -ForegroundColor Yellow

        # Check if JSON files are individual records or arrays
        $firstJson = Get-Content $jsonFiles[0].FullName -Raw -Encoding UTF8 | ConvertFrom-Json

        if ($firstJson -is [System.Collections.IEnumerable] -and $firstJson -isnot [string]) {
            # Already an array — upload directly
            Write-Host "  Uploading array JSON: $($jsonFiles[0].Name)" -ForegroundColor White
            $result = Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/upload/json" `
                -Method POST -Form @{ file = Get-Item $jsonFiles[0].FullName } -Headers $headers
            Write-Host "  Loaded $($result.total_loaded) records" -ForegroundColor Green
        } else {
            # Individual conversation records — transform and merge
            $transformed = [System.Collections.ArrayList]::new()
            foreach ($f in $jsonFiles) {
                $raw = Get-Content $f.FullName -Raw -Encoding UTF8
                $convo = $raw | ConvertFrom-Json

                # Auto-detect field mapping
                $id = if ($convo.ConversationId) { $convo.ConversationId }
                      elseif ($convo.id) { $convo.id }
                      else { [System.IO.Path]::GetFileNameWithoutExtension($f.Name) }

                $text = if ($convo.Content) { $convo.Content }
                        elseif ($convo.text) { $convo.text }
                        elseif ($convo.transcript) { $convo.transcript }
                        else { $convo | ConvertTo-Json -Depth 5 }

                # Build metadata from all non-text fields
                $meta = @{ source_file = $f.Name }
                $convo.PSObject.Properties | ForEach-Object {
                    $key = $_.Name
                    if ($key -notin @("Content", "text", "transcript") -and $null -ne $_.Value) {
                        $meta[$key] = [string]$_.Value
                    }
                }

                $null = $transformed.Add(@{
                    id   = $id
                    type = "call_transcript"
                    text = $text
                    metadata = $meta
                })
            }

            Write-Host "  Transformed $($transformed.Count) conversations" -ForegroundColor White
            $tempFile = Join-Path $env:TEMP "km_upload_$(Get-Date -Format 'yyyyMMddHHmmss').json"
            $transformed | ConvertTo-Json -Depth 10 -Compress |
                Out-File -FilePath $tempFile -Encoding UTF8

            try {
                $result = Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/upload/json" `
                    -Method POST -Form @{ file = Get-Item $tempFile } -Headers $headers
                Write-Host "  Loaded $($result.total_loaded) conversations" -ForegroundColor Green
            } finally {
                Remove-Item $tempFile -ErrorAction SilentlyContinue
            }
        }
    }

    # ── Audio files (batch upload) ──
    if ($audioFiles.Count -gt 0) {
        Write-Host ""
        Write-Host "Uploading $($audioFiles.Count) audio files (transcription via Content Understanding)..." -ForegroundColor Yellow

        # Upload in batches of 5 (API limit: max_concurrent_uploads)
        $batchSize = 5
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
                    -Method POST -Form @{ files = $fileItems } -Headers $headers | Out-Null
                $success += $batch.Count
                Write-Host "  Batch of $($batch.Count) submitted" -ForegroundColor Green
            } catch {
                Write-Host "  Batch FAILED: $_" -ForegroundColor Red
                $failed += $batch.Count
            }
        }
        Write-Host "  Audio: $success uploaded, $failed failed" -ForegroundColor $(if ($failed) { "Yellow" } else { "Green" })
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
                    -Method POST -Form @{ files = $fileItems } -Headers $headers | Out-Null
                $success += $batch.Count
                Write-Host "  Batch of $($batch.Count) submitted" -ForegroundColor Green
            } catch {
                Write-Host "  Batch FAILED: $_" -ForegroundColor Red
                $failed += $batch.Count
            }
        }
        Write-Host "  Documents: $success uploaded, $failed failed" -ForegroundColor $(if ($failed) { "Yellow" } else { "Green" })
    }

    Write-Host ""
    Write-Host "Data upload complete!" -ForegroundColor Green
}

# ══════════════════════════════════════════
# Option 2: Connect external data source
# ══════════════════════════════════════════
if ($ExternalSource) {
    $pyArgs = @("--type", $ExternalSource)
    if ($Name)             { $pyArgs += "--name", $Name }
    if ($Endpoint)         { $pyArgs += "--endpoint", $Endpoint }
    if ($Database)         { $pyArgs += "--database", $Database }
    if ($Table)            { $pyArgs += "--table", $Table }
    if ($ConnectionString) { $pyArgs += "--connection-string", $ConnectionString }

    python (Join-Path $PSScriptRoot "connect-data.py") @pyArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "External data source connection failed." -ForegroundColor Red
        exit 1
    }
}

# ══════════════════════════════════════════
# Option 3: Load built-in sample data
# ══════════════════════════════════════════
if ($UseSampleData) {
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

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
