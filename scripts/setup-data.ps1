#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Post-deployment data setup for Knowledge Mining.
.DESCRIPTION
    Unified script to load data into the app after deployment. Supports:
      1. Load a built-in scenario pack (contact-center, mortgage-application, telecom-analysis)
      2. Upload files from a custom folder (JSON, WAV, PDF, DOCX, etc.)
      3. Connect an external data source (Azure AI Search, Fabric, SQL, Synapse)

    Scenario packs ship with sample data under data/<scenario_folder>/.
    Raw files are processed through the Content Understanding pipeline:
      WAV/MP3 → transcribed → chunked → embedded → indexed
      JSON    → transformed → loaded → enriched → indexed
      PDF/DOCX → extracted → chunked → embedded → indexed

.EXAMPLE
    # Interactive — choose scenario or data source
    ./scripts/setup-data.ps1

    # Load a scenario pack
    ./scripts/setup-data.ps1 -Scenario contact-center
    ./scripts/setup-data.ps1 -Scenario mortgage-application
    ./scripts/setup-data.ps1 -Scenario telecom-analysis

    # Upload files from a custom folder
    ./scripts/setup-data.ps1 -DataPath "path/to/my/data"

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

    [string]$BackendUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Knowledge Mining — Data Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$projectRoot = Split-Path -Parent $PSScriptRoot

# ── Resolve backend URL ──
if ($BackendUrl -eq "http://localhost:8000") {
    $azdUrl = azd env get-value SERVICE_BACKEND_URI 2>$null
    if ($azdUrl) {
        Write-Host "Using deployed backend: $azdUrl" -ForegroundColor Yellow
        $BackendUrl = $azdUrl
    } else {
        Write-Host "Using local backend: $BackendUrl" -ForegroundColor Yellow
    }
}

# ── Auth token ──
$token = az account get-access-token --resource "api://$(azd env get-value AZURE_AD_CLIENT_ID 2>$null)" --query accessToken -o tsv 2>$null
if (-not $token) {
    $token = "test"
    Write-Host "Using test token (local dev)" -ForegroundColor Yellow
}
$headers = @{ Authorization = "Bearer $token" }

# ── Interactive mode if no params ──
if (-not $Scenario -and -not $DataPath -and -not $UseSampleData -and -not $ExternalSource) {
    Write-Host "Choose how to load data:" -ForegroundColor White
    Write-Host ""
    Write-Host "  1. Contact Center       — IT helpdesk call transcripts (JSON)" -ForegroundColor White
    Write-Host "  2. Mortgage Application  — Housing reports & contracts (PDF)" -ForegroundColor White
    Write-Host "  3. Telecom Analysis      — Call transcripts & audio (JSON + WAV)" -ForegroundColor White
    Write-Host "  4. Upload from a folder  — Bring your own files" -ForegroundColor White
    Write-Host "  5. Connect external source — AI Search, Fabric, SQL, Synapse" -ForegroundColor White
    Write-Host ""
    $choice = Read-Host "Enter choice (1-5)"

    switch ($choice) {
        "1" { $Scenario = "contact-center" }
        "2" { $Scenario = "mortgage-application" }
        "3" { $Scenario = "telecom-analysis" }
        "4" {
            $DataPath = Read-Host "Path to data folder (e.g., data/my_files)"
            if (-not [System.IO.Path]::IsPathRooted($DataPath)) {
                $DataPath = Join-Path $projectRoot $DataPath
            }
        }
        "5" {
            Write-Host ""
            & (Join-Path $PSScriptRoot "connect-data.ps1")
            exit $LASTEXITCODE
        }
        default {
            Write-Host "Invalid choice." -ForegroundColor Red
            exit 1
        }
    }
}

# ── Resolve scenario to data path ──
if ($Scenario) {
    $scenarioConfig = Get-Content (Join-Path $projectRoot "data" "config" "scenarios.json") -Raw | ConvertFrom-Json
    $pack = $scenarioConfig.scenarios.$Scenario

    if (-not $pack) {
        Write-Host "ERROR: Unknown scenario '$Scenario'." -ForegroundColor Red
        Write-Host "Available: contact-center, mortgage-application, telecom-analysis" -ForegroundColor Yellow
        exit 1
    }

    Write-Host ""
    Write-Host "Scenario: $($pack.name)" -ForegroundColor Cyan
    Write-Host "  $($pack.description)" -ForegroundColor White
    Write-Host ""

    $scenarioDataPath = Join-Path $projectRoot "data" $pack.data_folder

    if (-not (Test-Path $scenarioDataPath)) {
        Write-Host "ERROR: Scenario data folder not found: $scenarioDataPath" -ForegroundColor Red
        exit 1
    }

    # Contact Center has pre-processed data — use the direct seed path
    if ($pack.has_preprocessed -eq $true) {
        Write-Host "This scenario has pre-processed data. Loading via seed script..." -ForegroundColor Yellow
        Write-Host ""

        # Run seed-sample-data.py with the scenario data directory
        $env:KM_SCENARIO_DATA_DIR = $scenarioDataPath
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

    # ── Audio files ──
    if ($audioFiles.Count -gt 0) {
        Write-Host ""
        Write-Host "Uploading $($audioFiles.Count) audio files (transcription via Content Understanding)..." -ForegroundColor Yellow
        $success = 0; $failed = 0
        foreach ($f in $audioFiles) {
            Write-Host "  $($f.Name)..." -NoNewline
            try {
                Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/upload/document" `
                    -Method POST -Form @{ files = Get-Item $f.FullName } -Headers $headers | Out-Null
                Write-Host " done" -ForegroundColor Green
                $success++
            } catch {
                Write-Host " FAILED" -ForegroundColor Red
                $failed++
            }
        }
        Write-Host "  Audio: $success uploaded, $failed failed" -ForegroundColor $(if ($failed) { "Yellow" } else { "Green" })
        if ($success -gt 0) {
            Write-Host "  Audio files are processing in background — check Sources page for status." -ForegroundColor Cyan
        }
    }

    # ── Document files ──
    if ($docFiles.Count -gt 0) {
        Write-Host ""
        Write-Host "Uploading $($docFiles.Count) document files..." -ForegroundColor Yellow
        $success = 0; $failed = 0
        foreach ($f in $docFiles) {
            Write-Host "  $($f.Name)..." -NoNewline
            try {
                Invoke-RestMethod -Uri "$BackendUrl/api/ingestion/upload/document" `
                    -Method POST -Form @{ files = Get-Item $f.FullName } -Headers $headers | Out-Null
                Write-Host " done" -ForegroundColor Green
                $success++
            } catch {
                Write-Host " FAILED" -ForegroundColor Red
                $failed++
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
