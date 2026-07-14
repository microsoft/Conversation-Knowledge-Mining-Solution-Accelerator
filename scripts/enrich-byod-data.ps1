#Requires -Version 7.0
<#
.SYNOPSIS
    Enrich BYOD (Azure AI Search or Fabric) data sources with topics, summaries, entities, and key phrases.

.DESCRIPTION
    Runs the enrichment pipeline on external data sources to generate rich insights.
    Extracts topics, summaries, key phrases, and entities for all documents in the source.

.PARAMETER SourceId
    The source ID (Azure AI Search index name or Fabric connection ID).

.PARAMETER SourceType
    Type of external data source: 'azure_search' or 'fabric'.

.PARAMETER BatchSize
    Documents per batch for progress logging (default: 10).

.PARAMETER EnrichedOnly
    If specified, only enrich documents that haven't been enriched yet.

.EXAMPLE
    .\enrich-byod-data.ps1 -SourceId "my-search-index" -SourceType "azure_search"
    
.EXAMPLE
    .\enrich-byod-data.ps1 -SourceId "my-workspace-connection" -SourceType "fabric" -BatchSize 20
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$SourceId,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet("azure_search", "fabric")]
    [string]$SourceType,
    
    [Parameter(Mandatory=$false)]
    [int]$BatchSize = 10,
    
    [Parameter(Mandatory=$false)]
    [switch]$EnrichedOnly = $false
)

$ErrorActionPreference = "Stop"

# Get script paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

# Find Python executable
$pythonExe = $null
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $pythonExe = $pythonCmd.Source
    } else {
        Write-Host "❌ Python not found. Please install Python or activate the virtual environment." -ForegroundColor Red
        exit 1
    }
}

Write-Host "🔄 Starting BYOD Enrichment Pipeline" -ForegroundColor Cyan
Write-Host "   Source Type: $SourceType" -ForegroundColor Gray
Write-Host "   Source ID:   $SourceId" -ForegroundColor Gray
Write-Host "   Batch Size:  $BatchSize" -ForegroundColor Gray
Write-Host ""

# Run enrichment
Write-Host "Enriching documents... (this may take a few minutes)" -ForegroundColor Yellow
Write-Host ""

try {
    # Build enrichment command arguments
    $scriptPath = Join-Path $scriptDir "enrich_byod_data.py"
    $args = @(
        $scriptPath,
        "--source-id", $SourceId,
        "--source-type", $SourceType,
        "--batch-size", $BatchSize
    )
    
    if ($EnrichedOnly) {
        $args += "--enriched-only"
    }
    
    # Execute Python script and capture output
    $result = & $pythonExe @args 2>&1 | Out-String
    
    # Try to parse result as JSON
    $enrichmentResult = $null
    try {
        # Find JSON in output (might have debug output before it)
        $lines = $result -split "`n" | Where-Object { $_.Trim() }
        foreach ($line in $lines) {
            try {
                $enrichmentResult = $line | ConvertFrom-Json -ErrorAction Stop
                break
            } catch {
                # Not JSON, continue
            }
        }
    }
    catch {
        Write-Host "Could not parse enrichment result as JSON" -ForegroundColor Yellow
    }
    
    if (-not $enrichmentResult) {
        Write-Host "Python output:" -ForegroundColor Gray
        Write-Host $result -ForegroundColor Gray
    }
    
    if ($enrichmentResult) {
        Write-Host ""
        Write-Host "✅ Enrichment Complete" -ForegroundColor Green
        Write-Host ""
        Write-Host "Results:" -ForegroundColor Cyan
        Write-Host "  Documents Processed: $($enrichmentResult.documents_processed)" -ForegroundColor Gray
        Write-Host "  Successfully Enriched: $($enrichmentResult.enriched)" -ForegroundColor Green
        
        if ($enrichmentResult.errors -gt 0) {
            Write-Host "  Errors: $($enrichmentResult.errors)" -ForegroundColor Yellow
        }
        
        Write-Host "  Timestamp: $($enrichmentResult.timestamp)" -ForegroundColor Gray
        Write-Host ""
        
        if ($enrichmentResult.success) {
            Write-Host "✨ Insights generation will now use enriched metadata (topics, summaries, entities)" -ForegroundColor Green
            exit 0
        }
        else {
            Write-Host "⚠️  Enrichment had issues: $($enrichmentResult.error)" -ForegroundColor Yellow
            exit 1
        }
    }
    else {
        Write-Host "⚠️  Could not parse enrichment result" -ForegroundColor Yellow
        exit 1
    }
}
catch {
    Write-Host "❌ Enrichment failed: $_" -ForegroundColor Red
    Write-Host "Last exit code: $LASTEXITCODE" -ForegroundColor Red
    exit 1
}
